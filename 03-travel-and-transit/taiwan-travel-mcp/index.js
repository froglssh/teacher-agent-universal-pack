#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

// 跨平台家目錄：macOS/Linux 用 HOME、Windows 用 USERPROFILE（或 HOMEDRIVE+HOMEPATH），最後退回 os.homedir()
const USER_HOME =
  process.env.HOME ||
  process.env.USERPROFILE ||
  (process.env.HOMEDRIVE && process.env.HOMEPATH
    ? `${process.env.HOMEDRIVE}${process.env.HOMEPATH}`
    : os.homedir());

const CONFIG_PATH = path.join(
  USER_HOME,
  '.gemini',
  'config',
  'travel_transit_config.json'
);

function loadConfig() {
  let cfg = {
    tdx: {
      clientId: process.env.TDX_CLIENT_ID || '',
      clientSecret: process.env.TDX_CLIENT_SECRET || '',
    },
    exchangeRateApiKey: process.env.EXCHANGE_RATE_API_KEY || '',
    duffelApiKey: process.env.DUFFEL_API_KEY || '',
    googleMapsApiKey: process.env.GOOGLE_MAPS_API_KEY || '',
  };

  if (fs.existsSync(CONFIG_PATH)) {
    try {
      const fileData = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
      if (fileData.tdx) {
        if (!cfg.tdx.clientId && fileData.tdx.clientId) cfg.tdx.clientId = fileData.tdx.clientId;
        if (!cfg.tdx.clientSecret && fileData.tdx.clientSecret) cfg.tdx.clientSecret = fileData.tdx.clientSecret;
      }
      if (!cfg.exchangeRateApiKey && fileData.exchangeRateApiKey) {
        cfg.exchangeRateApiKey = fileData.exchangeRateApiKey;
      }
      if (!cfg.duffelApiKey && fileData.duffelApiKey) {
        cfg.duffelApiKey = fileData.duffelApiKey;
      }
      if (!cfg.googleMapsApiKey && fileData.googleMapsApiKey) {
        cfg.googleMapsApiKey = fileData.googleMapsApiKey;
      }
    } catch (e) {
      // ignore
    }
  }
  return cfg;
}

const TOKEN_CACHE_PATH = path.join(
  USER_HOME,
  '.gemini',
  'config',
  'tdx_token_cache.json'
);

let tdxTokenCache = {
  token: null,
  expiresAt: 0,
};

async function getTdxAccessToken(cfg) {
  if (!cfg.tdx.clientId || !cfg.tdx.clientSecret) {
    return null;
  }
  const now = Date.now();
  if (tdxTokenCache.token && tdxTokenCache.expiresAt > now + 60000) {
    return tdxTokenCache.token;
  }

  if (fs.existsSync(TOKEN_CACHE_PATH)) {
    try {
      const c = JSON.parse(fs.readFileSync(TOKEN_CACHE_PATH, 'utf8'));
      if (c.token && c.expiresAt > now + 60000) {
        tdxTokenCache.token = c.token;
        tdxTokenCache.expiresAt = c.expiresAt;
        return c.token;
      }
    } catch (e) {}
  }

  const tokenUrl = 'https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token';
  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: cfg.tdx.clientId,
    client_secret: cfg.tdx.clientSecret,
  });

  const resp = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`TDX Token 取得失敗 (${resp.status}): ${txt}`);
  }

  const data = await resp.json();
  tdxTokenCache.token = data.access_token;
  tdxTokenCache.expiresAt = now + (data.expires_in || 86400) * 1000;
  try {
    fs.writeFileSync(
      TOKEN_CACHE_PATH,
      JSON.stringify({
        token: tdxTokenCache.token,
        expiresAt: tdxTokenCache.expiresAt,
      }),
      'utf8'
    );
  } catch (e) {}
  return tdxTokenCache.token;
}

// 常見機場 IATA 字典映射
const AIRPORT_MAP = {
  '台北': 'TPE',
  '桃園': 'TPE',
  '松山': 'TSA',
  '高雄': 'KHH',
  '台中': 'RMQ',
  '東京': 'NRT',
  '成田': 'NRT',
  '羽田': 'HND',
  '大阪': 'KIX',
  '關西': 'KIX',
  '京都': 'KIX',
  '福岡': 'FUK',
  '沖繩': 'OKA',
  '札幌': 'CTS',
  '首爾': 'ICN',
  '仁川': 'ICN',
  '金浦': 'GMP',
  '釜山': 'PUS',
  '香港': 'HKG',
  '澳門': 'MFM',
  '曼谷': 'BKK',
  '新加坡': 'SIN',
  '吉隆坡': 'KUL',
  '倫敦': 'LHR',
  '巴黎': 'CDG',
  '紐約': 'JFK',
  '舊金山': 'SFO',
  '洛杉磯': 'LAX',
};

function resolveAirportCode(str) {
  if (!str) return 'TPE';
  const clean = str.trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(clean)) return clean;
  for (const [key, code] of Object.entries(AIRPORT_MAP)) {
    if (str.includes(key)) return code;
  }
  return clean;
}

// 建立 MCP Server
// 票價快取：避免重複查詢燒掉 TDX 免費額度
const __fareCache = new Map(); // key: oid-did -> { price, at }
const __fareBlockedUntil = { t: 0 };
const server = new Server(
  {
    name: 'taiwan-travel-mcp',
    version: '1.1.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'calculate_route',
        description:
          '使用 Google Maps 最新版 Routes API 計算兩地之間的交通路線、距離、行車/騎乘時間與導航指示。',
        inputSchema: {
          type: 'object',
          properties: {
            origin: {
              type: 'string',
              description: '出發地點名稱或地址（例如: 台北車站、台北 101）',
            },
            destination: {
              type: 'string',
              description: '目的地名稱或地址（例如: 台北市立松山高中、九份老街）',
            },
            mode: {
              type: 'string',
              enum: ['DRIVE', 'TWO_WHEELER', 'BICYCLE', 'WALK'],
              description: '交通方式：DRIVE(開車/計程車)、TWO_WHEELER(機車)、BICYCLE(自行車)、WALK(步行)。預設 DRIVE',
              default: 'DRIVE',
            },
          },
          required: ['origin', 'destination'],
        },
      },
      {
        name: 'search_flights',
        description:
          '透過 Duffel API 搜尋全球即時航班、機票價格與比價資訊（支援各國航空公司即時優惠報價）。',
        inputSchema: {
          type: 'object',
          properties: {
            origin: {
              type: 'string',
              description: '出發機場代碼或城市名（例如: TPE, 台北, 松山, KHH）',
            },
            destination: {
              type: 'string',
              description: '抵達機場代碼或城市名（例如: NRT, 東京, 大阪, KIX, ICN, BKK）',
            },
            departureDate: {
              type: 'string',
              description: '出發日期 (格式: YYYY-MM-DD，例如: 2026-12-05)',
            },
            returnDate: {
              type: 'string',
              description: '可選：回程日期 (格式: YYYY-MM-DD，若為來回機票)',
            },
            cabinClass: {
              type: 'string',
              enum: ['economy', 'premium_economy', 'business', 'first'],
              description: '艙等代碼 (預設 economy)',
              default: 'economy',
            },
            passengers: {
              type: 'number',
              description: '成人旅客人數 (預設 1)',
              default: 1,
            },
          },
          required: ['origin', 'destination', 'departureDate'],
        },
      },
      {
        name: 'get_exchange_rates',
        description:
          '查詢全球即時外幣匯率（以新台幣 TWD 或指定貨幣為基準），包含日圓(JPY)、美金(USD)、歐元(EUR)、韓元(KRW)、泰銖(THB)等旅遊熱門幣別，免金鑰即可使用。',
        inputSchema: {
          type: 'object',
          properties: {
            base: {
              type: 'string',
              description: '基準貨幣代碼，預設為 "TWD"，亦可輸入 USD, JPY, EUR 等',
              default: 'TWD',
            },
            target: {
              type: 'string',
              description: '可選：若只需查詢特定單一目標貨幣（如 JPY, USD）',
            },
            amount: {
              type: 'number',
              description: '可選：換算金額，例如 10000（計算換算後的總額）',
            },
          },
        },
      },
      {
        name: 'convert_currency',
        description: '精確換算兩國貨幣金額，例如將 50000 日圓(JPY)換算為新台幣(TWD)。',
        inputSchema: {
          type: 'object',
          properties: {
            amount: {
              type: 'number',
              description: '兌換金額',
            },
            from: {
              type: 'string',
              description: '原始貨幣代碼（例如 JPY, USD, EUR）',
            },
            to: {
              type: 'string',
              description: '目標貨幣代碼（例如 TWD, USD, JPY）',
            },
          },
          required: ['amount', 'from', 'to'],
        },
      },
      {
        name: 'tdx_status',
        description:
          '檢查台灣交通部 TDX (運輸資料流通服務) API 憑證設定狀態，並提供註冊與串接指引。',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'tdx_query_bus',
        description:
          '透過 TDX 查詢台灣指定縣市與路線的公車預估到站時間或動態。需已配置 TDX Client ID/Secret。',
        inputSchema: {
          type: 'object',
          properties: {
            city: {
              type: 'string',
              description:
                '縣市代碼（英文），例如 Taipei, NewTaipei, Taichung, Tainan, Kaohsiung',
            },
            routeName: {
              type: 'string',
              description: '公車路線名稱，例如 307, 藍2, 基隆路幹線',
            },
            direction: {
              type: 'number',
              description: '去返程：0 去程，1 返程（選填）',
            },
          },
          required: ['city', 'routeName'],
        },
      },
      {
        name: 'tdx_query_railway',
        description:
          '透過 TDX 查詢高鐵 (THSR) 或台鐵 (TRA) 當日班次時刻表或起迄站列車時刻。',
        inputSchema: {
          type: 'object',
          properties: {
            type: {
              type: 'string',
              enum: ['THSR', 'TRA'],
              description: '鐵路系統類型：THSR (高鐵) 或 TRA (台鐵)',
            },
            originStationName: {
              type: 'string',
              description: '出發站站名（如：台北、板橋、台中、左營）',
            },
            destinationStationName: {
              type: 'string',
              description: '抵達站站名（如：台中、左營、花蓮、台東）',
            },
          },
          required: ['type'],
        },
      },
      {
        name: 'query_weather',
        description:
          '查詢台灣各縣市或全球各大城市之即時天氣預報（包含即時氣溫、體感溫度、濕度、降雨量、今日溫差與天候狀況）。',
        inputSchema: {
          type: 'object',
          properties: {
            city: {
              type: 'string',
              description: '城市名稱或縣市名稱（例如: 台北, 新北, 台中, 高雄, 花蓮, 宜蘭, 東京, 大阪, 首爾, 紐約）',
              default: '台北',
            },
          },
          required: ['city'],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const cfg = loadConfig();

  try {
    if (name === 'calculate_route') {
      const key = cfg.googleMapsApiKey || process.env.GOOGLE_MAPS_API_KEY;
      if (!key) {
        return {
          content: [{ type: 'text', text: '⚠️ 尚未配置 Google Maps API Key。請在 travel_transit_config.json 設定 googleMapsApiKey。' }],
        };
      }
      const { origin, destination, mode = 'DRIVE' } = args;
      const url = 'https://routes.googleapis.com/directions/v2:computeRoutes';
      const m = (mode || 'DRIVE').toUpperCase();

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Goog-Api-Key': key,
          'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters,routes.description,routes.legs.steps.navigationInstruction,routes.legs.steps.localizedValues'
        },
        body: JSON.stringify({
          origin: { address: origin },
          destination: { address: destination },
          travelMode: m,
          routingPreference: m === 'DRIVE' ? 'TRAFFIC_AWARE' : undefined
        })
      });

      if (!res.ok) {
        const errTxt = await res.text();
        return { content: [{ type: 'text', text: `Google Routes API 查詢失敗 (${res.status}): ${errTxt}` }] };
      }

      const data = await res.json();
      const r = data.routes?.[0];
      if (!r) {
        return { content: [{ type: 'text', text: `查無從【${origin}】到【${destination}】的路線方案。` }] };
      }

      const mins = Math.round(parseInt(r.duration) / 60);
      const km = (r.distanceMeters / 1000).toFixed(1);
      let out = `🗺️ 交通路線規劃 (Google Routes API 新版)\n`;
      out += `• 起點: ${origin} ➜ 終點: ${destination}\n`;
      out += `• 模式: ${m} | 總距離: ${km} 公里 | 預估時間: ${mins} 分鐘\n`;
      if (r.description) out += `• 主要路段: ${r.description}\n`;
      out += `\n📍 主要導航指示:\n`;

      if (r.legs?.[0]?.steps) {
        r.legs[0].steps.slice(0, 8).forEach((s, idx) => {
          if (s.navigationInstruction?.instructions) {
            const dist = s.localizedValues?.distance?.text || '';
            out += `  ${idx + 1}. ${s.navigationInstruction.instructions} (${dist})\n`;
          }
        });
      }

      return { content: [{ type: 'text', text: out }] };
    }

    if (name === 'search_flights') {
      if (!cfg.duffelApiKey) {
        return {
          content: [
            {
              type: 'text',
              text: `⚠️ 尚未配置 Duffel API Key。請在 ~/.gemini/config/travel_transit_config.json 中填入 "duffelApiKey"。`,
            },
          ],
        };
      }

      const origin = resolveAirportCode(args.origin);
      const destination = resolveAirportCode(args.destination);
      const departureDate = args.departureDate;
      const cabinClass = args.cabinClass || 'economy';
      const passengerCount = typeof args.passengers === 'number' ? args.passengers : 1;

      const slices = [
        {
          origin,
          destination,
          departure_date: departureDate,
        },
      ];

      if (args.returnDate) {
        slices.push({
          origin: destination,
          destination: origin,
          departure_date: args.returnDate,
        });
      }

      const passengers = [];
      for (let i = 0; i < passengerCount; i++) {
        passengers.push({ type: 'adult' });
      }

      const body = {
        data: {
          slices,
          passengers,
          cabin_class: cabinClass,
        },
      };

      const duffelUrl = 'https://api.duffel.com/air/offer_requests?return_offers=true';
      const dResp = await fetch(duffelUrl, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${cfg.duffelApiKey}`,
          'Duffel-Version': 'v2',
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!dResp.ok) {
        const errTxt = await dResp.text();
        return {
          content: [{ type: 'text', text: `Duffel 航班查詢失敗 (${dResp.status}): ${errTxt}` }],
        };
      }

      const resData = await dResp.json();
      const offers = resData.data?.offers || [];
      if (offers.length === 0) {
        return {
          content: [
            {
              type: 'text',
              text: `✈️ 查無【${origin} ➜ ${destination}】在 ${departureDate} 的可用航班優惠。請確認日期或更換鄰近機場再試。`,
            },
          ],
        };
      }

      // 排序票價
      offers.sort((a, b) => parseFloat(a.total_amount) - parseFloat(b.total_amount));

      let out = `✈️ 【${origin} ➜ ${destination}】機票比價與航班搜尋結果\n`;
      out += `出發日期: ${departureDate} | 艙等: ${cabinClass} | 旅客: ${passengerCount} 位成人\n`;
      out += `共搜尋到 ${offers.length} 筆航班方案，為您精選前 6 筆最優惠選擇：\n\n`;

      const topOffers = offers.slice(0, 6);
      topOffers.forEach((o, idx) => {
        const owner = o.owner?.name || '航空公司';
        const price = `${parseFloat(o.total_amount).toLocaleString()} ${o.total_currency}`;
        const slice = o.slices?.[0];
        const segments = slice?.segments || [];
        const firstSeg = segments[0];
        const lastSeg = segments[segments.length - 1];
        const stops = segments.length > 1 ? `轉機 ${segments.length - 1} 次` : '直飛';
        const depTime = firstSeg?.departing_at?.replace('T', ' ')?.slice(0, 16);
        const arrTime = lastSeg?.arriving_at?.replace('T', ' ')?.slice(0, 16);

        out += `${idx + 1}. 【${owner}】\n`;
        out += `   • 航程：${firstSeg?.origin?.iata_code} (${depTime}) ➜ ${lastSeg?.destination?.iata_code} (${arrTime})\n`;
        out += `   • 類型：${stops}\n`;
        out += `   • 票價：💰 ${price}\n\n`;
      });

      return {
        content: [{ type: 'text', text: out }],
      };
    }

    if (name === 'get_exchange_rates') {
      const base = (args?.base || 'TWD').toUpperCase();
      const target = args?.target ? args.target.toUpperCase() : null;
      const amount = typeof args?.amount === 'number' ? args.amount : 1;

      let apiUrl = `https://open.er-api.com/v6/latest/${base}`;
      if (cfg.exchangeRateApiKey) {
        apiUrl = `https://v6.exchangerate-api.com/v6/${cfg.exchangeRateApiKey}/latest/${base}`;
      }

      const res = await fetch(apiUrl);
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `取得匯率資料失敗：HTTP ${res.status}` }],
        };
      }
      const data = await res.json();
      if (data.result !== 'success') {
        return {
          content: [{ type: 'text', text: `匯率 API 回傳錯誤：${JSON.stringify(data)}` }],
        };
      }

      const rates = data.rates || {};
      const popular = ['USD', 'JPY', 'EUR', 'KRW', 'THB', 'CNY', 'HKD', 'GBP', 'AUD', 'SGD', 'VND'];

      let summary = `💰 即時外幣匯率報告 (基準貨幣: ${base})\n`;
      summary += `更新時間 (UTC): ${data.time_last_update_utc}\n\n`;

      if (target) {
        const rate = rates[target];
        if (!rate) {
          return {
            content: [{ type: 'text', text: `找不到貨幣代碼 ${target} 的匯率資訊。` }],
          };
        }
        const converted = (amount * rate).toFixed(4);
        const reverseRate = (1 / rate).toFixed(4);
        summary += `• 1 ${base} = ${rate} ${target}\n`;
        summary += `• 1 ${target} = ${reverseRate} ${base}\n`;
        if (amount !== 1) {
          summary += `💵 試算：${amount} ${base} = ${converted} ${target}\n`;
        }
      } else {
        summary += `常見旅遊幣別速查 (1 ${base} 可兌換)：\n`;
        for (const cur of popular) {
          if (rates[cur]) {
            const r = rates[cur];
            const inv = (1 / r).toFixed(4);
            summary += `• ${cur.padEnd(4)}: ${r.toFixed(4)} (相當於 1 ${cur} ≈ ${inv} ${base})\n`;
          }
        }
        if (amount !== 1) {
          summary += `\n💵 試算 ${amount} ${base} 兌換結果：\n`;
          for (const cur of ['USD', 'JPY', 'EUR', 'KRW', 'THB']) {
            if (rates[cur]) {
              summary += `• ${amount} ${base} ≈ ${(amount * rates[cur]).toFixed(2)} ${cur}\n`;
            }
          }
        }
      }

      return {
        content: [{ type: 'text', text: summary }],
      };
    }

    if (name === 'convert_currency') {
      const { amount, from, to } = args;
      const baseFrom = from.toUpperCase();
      const targetTo = to.toUpperCase();

      let apiUrl = `https://open.er-api.com/v6/latest/${baseFrom}`;
      if (cfg.exchangeRateApiKey) {
        apiUrl = `https://v6.exchangerate-api.com/v6/${cfg.exchangeRateApiKey}/latest/${baseFrom}`;
      }

      const res = await fetch(apiUrl);
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `取得匯率資料失敗：HTTP ${res.status}` }],
        };
      }
      const data = await res.json();
      const rate = data.rates?.[targetTo];
      if (!rate) {
        return {
          content: [{ type: 'text', text: `無法取得 ${baseFrom} 兌換 ${targetTo} 的匯率。` }],
        };
      }

      const converted = (amount * rate).toFixed(2);
      const rev = (1 / rate).toFixed(4);
      const text = `💱 貨幣換算結果：
• 兌換金額：${amount.toLocaleString()} ${baseFrom} = ${Number(converted).toLocaleString()} ${targetTo}
• 當前匯率：1 ${baseFrom} = ${rate.toFixed(4)} ${targetTo} (1 ${targetTo} ≈ ${rev} ${baseFrom})
• 更新時間：${data.time_last_update_utc}`;

      return {
        content: [{ type: 'text', text }],
      };
    }

    if (name === 'tdx_status') {
      const hasId = Boolean(cfg.tdx.clientId);
      const hasSecret = Boolean(cfg.tdx.clientSecret);

      if (hasId && hasSecret) {
        try {
          const token = await getTdxAccessToken(cfg);
          return {
            content: [
              {
                type: 'text',
                text: `✅ TDX (運輸資料流通服務) API 驗證成功！\n已成功取得 Access Token，全台高鐵、台鐵、公車與景點查詢功能已正式上線。`,
              },
            ],
          };
        } catch (err) {
          return {
            content: [
              {
                type: 'text',
                text: `⚠️ TDX API 憑證驗證失敗：${err.message}\n請檢查 Client ID 與 Client Secret 是否正確。`,
              },
            ],
          };
        }
      } else {
        return {
          content: [
            {
              type: 'text',
              text: `⚠️ TDX (台灣交通運輸資料) API 尚未配置 Client ID / Secret。`,
            },
          ],
        };
      }
    }

    if (name === 'tdx_query_bus') {
      const token = await getTdxAccessToken(cfg);
      if (!token) {
        return {
          content: [
            {
              type: 'text',
              text: `⚠️ 尚未設定 TDX 憑證，無法查詢公車即時動態。請先執行 tdx_status 取得設定指引。`,
            },
          ],
        };
      }

      const { city, routeName, direction } = args;
      let url = `https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/${city}/${encodeURIComponent(routeName)}?$format=JSON&$top=30`;
      if (typeof direction === 'number') {
        url += `&$filter=Direction eq ${direction}`;
      }

      const res = await fetch(url, {
        headers: { authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        return {
          content: [{ type: 'text', text: `TDX 公車查詢失敗：HTTP ${res.status}` }],
        };
      }

      const list = await res.json();
      if (!Array.isArray(list) || list.length === 0) {
        return {
          content: [{ type: 'text', text: `在 ${city} 查無路線【${routeName}】的即時公車到站資訊。` }],
        };
      }

      let out = `🚌 【${city}】${routeName} 即時到站動態：\n\n`;
      list.slice(0, 20).forEach((item) => {
        const stop = item.StopName?.Zh_tw || '未知站名';
        let status = '未發車';
        if (typeof item.EstimateTime === 'number') {
          const mins = Math.round(item.EstimateTime / 60);
          status = mins <= 1 ? '即將進站' : `約 ${mins} 分鐘`;
        } else if (item.StopStatus === 1) {
          status = '尚未發車';
        } else if (item.StopStatus === 2) {
          status = '交管不停靠';
        } else if (item.StopStatus === 3) {
          status = '末班車已過';
        }
        out += `• ${stop}：${status}\n`;
      });

      return {
        content: [{ type: 'text', text: out }],
      };
    }

    if (name === 'tdx_query_railway') {
      const token = await getTdxAccessToken(cfg);
      if (!token) {
        return {
          content: [
            {
              type: 'text',
              text: `⚠️ 尚未設定 TDX 憑證，無法查詢高鐵/台鐵時刻。請先執行 tdx_status 取得設定指引。`,
            },
          ],
        };
      }

      // 支援多種常見參數名稱別名（避免不同 Agent 傳入不同欄位名稱）
      const origRaw =
        args.originStationName ||
        args.originStation ||
        args.origin ||
        args.fromStation ||
        args.from ||
        args.start ||
        '';
      const destRaw =
        args.destinationStationName ||
        args.destinationStation ||
        args.destination ||
        args.toStation ||
        args.to ||
        args.end ||
        '';
      const type = (args.type || args.railwayType || 'THSR').toUpperCase();

      // 站名正規化：台/臺 互通、去空白
      const norm = (s) =>
        String(s || '').replace(/\s/g, '').replace(/台/g, '臺').trim();
      const wantO = norm(origRaw);
      const wantD = norm(destRaw);
      const hit = (stationName, want) => {
        const n = norm(stationName);
        return n === want || n.includes(want) || want.includes(n);
      };

      if (type === 'THSR') {
        const url =
          'https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/DailyTimetable/Today?$format=JSON';
        const res = await fetch(url, { headers: { authorization: `Bearer ${token}` } });
        if (!res.ok) {
          return { content: [{ type: 'text', text: `高鐵資料查詢失敗：HTTP ${res.status}` }] };
        }
        const data = await res.json();

        const rows = [];
        for (const t of data) {
          const info = t.DailyTrainInfo || {};
          const stops = t.StopTimes || [];
          
          let idxO = -1;
          let idxD = -1;

          if (wantO) {
            idxO = stops.findIndex((s) => hit(s.StationName?.Zh_tw, wantO));
            if (idxO < 0) continue; // 出發站不在停靠清單中，跳過此車次
          } else {
            idxO = 0;
          }

          if (wantD) {
            idxD = stops.findIndex((s) => hit(s.StationName?.Zh_tw, wantD));
            if (idxD < 0) continue; // 抵達站不在停靠清單中，跳過此車次
          } else {
            idxD = stops.length - 1;
          }

          // 核心防呆：出發站在抵達站之後（方向相反），或起訖為同一站，直接排除！
          if (idxD <= idxO) continue;

          const toM = (s) => {
            const [h, m] = String(s || '0:0').split(':').map(Number);
            return h * 60 + (m || 0);
          };
          let d = toM(stops[idxD].ArrivalTime) - toM(stops[idxO].DepartureTime);
          if (d < 0) d += 24 * 60;
          const durStr = d ? `${Math.floor(d / 60) ? Math.floor(d / 60) + ' 小時 ' : ''}${d % 60} 分` : '';

          const dirText = info.Direction === 0 ? '南下' : '北上';

          rows.push({
            train: info.TrainNo,
            direction: dirText,
            from: stops[idxO].StationName?.Zh_tw,
            to: stops[idxD].StationName?.Zh_tw,
            dep: stops[idxO].DepartureTime,
            arr: stops[idxD].ArrivalTime,
            dur: durStr,
            oid: stops[idxO].StationID,
            did: stops[idxD].StationID,
          });
        }
        rows.sort((a, b) => String(a.dep || '').localeCompare(String(b.dep || '')));

        const displayO = origRaw || (rows[0] ? rows[0].from : '');
        const displayD = destRaw || (rows[0] ? rows[0].to : '');
        const head =
          wantO && wantD
            ? `🚄 高鐵 ${displayO} ➜ ${displayD}（今日 ${rows.length} 班直達）`
            : `🚄 台灣高鐵 (THSR) 今日車次（共 ${rows.length} 班）`;

        if (!rows.length) {
          return {
            content: [
              {
                type: 'text',
                text: `${head}\n\n⚠️ 查無此區間的直達車次。可能是站名不符，或該區間需轉乘。\n可用站名：南港、臺北、板橋、桃園、新竹、苗栗、臺中、彰化、雲林、嘉義、臺南、左營`,
              },
            ],
          };
        }

        // 票價（成人標準票），失敗則略過
        let fareLine = '';
        if (wantO && wantD && rows[0]?.oid && rows[0]?.did) {
          try {
            const key = `${rows[0].oid}-${rows[0].did}`;
            const cached = __fareCache.get(key);
            const now = Date.now();
            if (cached && now - cached.at < 12 * 3600 * 1000) {
              fareLine = `\n💰 票價：${cached.text}`;
            } else if (now > __fareBlockedUntil.t) {
              const fu = `https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/ODFare/${rows[0].oid}/to/${rows[0].did}?$format=JSON`;
              const fr = await fetch(fu, { headers: { authorization: `Bearer ${token}` } });
              if (fr.status === 429) {
                __fareBlockedUntil.t = now + 10 * 60 * 1000;
              } else if (fr.ok) {
                const fd = await fr.json();
                const fares = (fd?.[0]?.Fares || []).filter((f) => /成人|全票/.test(f.TicketType || ''));
                if (fares.length) {
                  const text = fares.map((f) => `${f.TicketType} ${f.Price} 元`).join('、');
                  __fareCache.set(key, { text, at: now });
                  fareLine = `\n💰 票價：${text}`;
                }
              }
            }
          } catch (e) {
            /* 票價非必要，失敗不影響班次 */
          }
        }

        let out = `${head}${fareLine}\n\n`;
        rows.slice(0, 50).forEach((r) => {
          out += `• ${r.dep} ${r.from} → ${r.arr} ${r.to}（車次 ${r.train}，[${r.direction}]，行車 ${r.dur}）\n`;
        });
        if (rows.length > 50) out += `…其餘 ${rows.length - 50} 班省略\n`;
        if (!wantO || !wantD) {
          out += `\n提示：指定出發站與抵達站（例如 originStationName: "台北", destinationStationName: "左營"）可自動篩選單一方向直達班次。`;
        }
        return { content: [{ type: 'text', text: out }] };
      }

      if (type === 'TRA') {
        const url =
          'https://tdx.transportdata.tw/api/basic/v2/Rail/TRA/DailyTimetable/Today?$format=JSON';
        const res = await fetch(url, { headers: { authorization: `Bearer ${token}` } });
        if (!res.ok) {
          return { content: [{ type: 'text', text: `台鐵資料查詢失敗：HTTP ${res.status}` }] };
        }
        const data = await res.json();
        const rows = [];
        for (const t of data) {
          const info = t.DailyTrainInfo || {};
          const stops = t.StopTimes || [];
          let idxO = -1;
          let idxD = -1;
          if (wantO) {
            idxO = stops.findIndex((s) => hit(s.StationName?.Zh_tw, wantO));
            if (idxO < 0) continue;
          } else {
            idxO = 0;
          }
          if (wantD) {
            idxD = stops.findIndex((s) => hit(s.StationName?.Zh_tw, wantD));
            if (idxD < 0) continue;
          } else {
            idxD = stops.length - 1;
          }
          if (idxD <= idxO) continue;
          rows.push({
            train: info.TrainNo,
            type: info.TrainTypeName?.Zh_tw || '',
            from: stops[idxO].StationName?.Zh_tw,
            to: stops[idxD].StationName?.Zh_tw,
            dep: stops[idxO].DepartureTime,
            arr: stops[idxD].ArrivalTime,
          });
        }
        rows.sort((a, b) => String(a.dep || '').localeCompare(String(b.dep || '')));
        const displayO = origRaw || (rows[0] ? rows[0].from : '起站');
        const displayD = destRaw || (rows[0] ? rows[0].to : '迄站');
        if (!rows.length) {
          return {
            content: [
              { type: 'text', text: `🚆 台鐵：查無 ${displayO} → ${displayD} 的直達班次（今日）。` },
            ],
          };
        }
        let out = `🚆 台鐵 ${displayO} ➜ ${displayD}（今日 ${rows.length} 班）\n\n`;
        rows.slice(0, 40).forEach((r) => {
          out += `• ${r.dep} ${r.from} → ${r.arr} ${r.to}（${r.train}${r.type ? '，' + r.type : ''}）\n`;
        });
        if (rows.length > 40) out += `…其餘 ${rows.length - 40} 班省略\n`;
        return { content: [{ type: 'text', text: out }] };
      }

      return {
        content: [{ type: 'text', text: `未支援的鐵路類型：${type}（可用 THSR / TRA）` }],
      };
    }

    if (name === 'query_weather') {
      const city = String(args.city || args.location || args.query || '台北').trim();
      const cityMap = {
        '台北': 'Taipei', '臺北': 'Taipei', '台北市': 'Taipei', '臺北市': 'Taipei',
        '新北': 'New Taipei', '新北市': 'New Taipei', '基隆': 'Keelung', '基隆市': 'Keelung',
        '桃園': 'Taoyuan', '桃園市': 'Taoyuan', '新竹': 'Hsinchu', '新竹市': 'Hsinchu', '新竹縣': 'Hsinchu',
        '苗栗': 'Miaoli', '苗栗縣': 'Miaoli', '台中': 'Taichung', '臺中': 'Taichung', '台中市': 'Taichung', '臺中市': 'Taichung',
        '彰化': 'Changhua', '彰化縣': 'Changhua', '南投': 'Nantou', '南投縣': 'Nantou', '雲林': 'Yunlin', '雲林縣': 'Yunlin',
        '嘉義': 'Chiayi', '嘉義市': 'Chiayi', '嘉義縣': 'Chiayi', '台南': 'Tainan', '臺南': 'Tainan', '台南市': 'Tainan', '臺南市': 'Tainan',
        '高雄': 'Kaohsiung', '高雄市': 'Kaohsiung', '屏東': 'Pingtung', '屏東縣': 'Pingtung',
        '宜蘭': 'Yilan', '宜蘭縣': 'Yilan', '花蓮': 'Hualien', '花蓮縣': 'Hualien',
        '台東': 'Taitung', '臺東': 'Taitung', '台東縣': 'Taitung', '臺東縣': 'Taitung',
        '澎湖': 'Penghu', '金門': 'Kinmen', '連江': 'Matsu', '馬祖': 'Matsu',
        '東京': 'Tokyo', '大阪': 'Osaka', '京都': 'Kyoto', '福岡': 'Fukuoka', '札幌': 'Sapporo', '沖繩': 'Okinawa',
        '首爾': 'Seoul', '釜山': 'Busan', '香港': 'Hong Kong', '澳門': 'Macau', '曼谷': 'Bangkok', '新加坡': 'Singapore'
      };
      const q = cityMap[city] || city;
      const url = `https://wttr.in/${encodeURIComponent(q)}?format=j1`;
      try {
        const res = await fetch(url, { headers: { 'User-Agent': 'curl/8.0' } });
        if (!res.ok) {
          return { content: [{ type: 'text', text: `⚠️ 無法取得【${city}】的天氣資訊 (HTTP ${res.status})` }] };
        }
        const data = await res.json();
        const cur = data.current_condition?.[0];
        if (!cur) {
          return { content: [{ type: 'text', text: `⚠️ 查無【${city}】即時氣候資料。` }] };
        }

        const weatherDescMap = {
          'Sunny': '晴天 ☀️',
          'Clear': '晴朗 ☀️',
          'Partly cloudy': '晴時多雲 ⛅',
          'Partly Cloudy': '晴時多雲 ⛅',
          'Cloudy': '多雲 ☁️',
          'Overcast': '陰天 ☁️',
          'Mist': '薄霧 🌫️',
          'Fog': '濃霧 🌫️',
          'Patchy rain possible': '局部降雨機率 🌦️',
          'Patchy rain nearby': '附近有零星短暫雨 🌦️',
          'Light rain': '小雨 🌧️',
          'Moderate rain': '中雨 🌧️',
          'Heavy rain': '大雨 🌧️',
          'Light drizzle': '毛毛細雨 🌦️',
          'Light rain shower': '局部短暫陣雨 🌦️',
          'Thundery outbreaks possible': '可能有雷陣雨 ⛈️'
        };
        const rawDesc = cur.weatherDesc?.[0]?.value || '';
        const descZh = weatherDescMap[rawDesc] || rawDesc;

        let out = `🌤️ 【${city}】即時氣象報告\n`;
        out += `• 當前氣候：${descZh}\n`;
        out += `• 即時氣溫：${cur.temp_C} °C（體感溫度: ${cur.FeelsLikeC} °C）\n`;
        out += `• 相對濕度：${cur.humidity} %\n`;
        out += `• 降雨量　：${cur.precipMM} mm\n`;
        out += `• 當前風速：時速 ${cur.windspeedKmph} 公里\n`;

        const today = data.weather?.[0];
        if (today) {
          out += `• 今日溫差：最高溫 ${today.maxtempC} °C / 最低溫 ${today.mintempC} °C\n`;
        }
        return { content: [{ type: 'text', text: out }] };
      } catch (err) {
        return { content: [{ type: 'text', text: `查詢天氣失敗: ${err.message}` }], isError: true };
      }
    }

    return {
      content: [{ type: 'text', text: `未知的工具名稱: ${name}` }],
      isError: true,
    };
  } catch (err) {
    return {
      content: [{ type: 'text', text: `執行錯誤: ${err.message}` }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error('Server error:', err);
  process.exit(1);
});
