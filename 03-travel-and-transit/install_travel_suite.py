#!/usr/bin/env python3
"""
老師專用：生活、交通、機票比價與即時匯率工具箱一鍵安裝器 (純淨開源教學版)
功能：
1. 自動部署 taiwan-travel-mcp 伺服器與 travel-cli 命令列指令
2. 自動部署 Antigravity 專用工具規格檔 (Schemas)
3. 自動建立乾淨的空白設定檔 ~/.gemini/config/travel_transit_config.json (絕無私人金鑰)
4. 自動偵測本機各大 Agent (Antigravity, Claude Code, Codex, OpenCode, Hermes, Cursor) 並注入配置
5. 提示老師依照 TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md 填入自己申請的免費金鑰
"""
import os
import sys
import json
import shutil
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
HOME = Path.home()
NODE_PATH = shutil.which("node") or "/usr/local/bin/node"

print("==================================================================")
print("🎒 老師專屬：AI Agent 生活、交通、機票比價與氣象工具箱一鍵安裝器")
print("==================================================================")

# 1. 建立必要目錄
CONFIG_DIR = HOME / ".gemini" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
MCP_TARGET_DIR = HOME / ".gemini" / "antigravity" / "mcp" / "taiwan-travel-mcp"
MCP_TARGET_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR = HOME / ".local" / "bin"
BIN_DIR.mkdir(parents=True, exist_ok=True)

# 2. 建立設定檔 (若已存在則不覆蓋，若不存在則建立乾淨空白範本)
cfg_target = CONFIG_DIR / "travel_transit_config.json"
if not cfg_target.exists():
    cfg_data = {
        "tdx": {
            "clientId": "",
            "clientSecret": "",
        },
        "exchangeRateApiKey": "",
        "duffelApiKey": "",
        "googleMapsApiKey": "",
    }
    with open(cfg_target, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
    print(f"✅ 已建立空白金鑰設定檔: {cfg_target}")
else:
    print(f"ℹ️ 設定檔已存在，保留現有金鑰設定: {cfg_target}")

# 3. 部署 taiwan-travel-mcp 伺服器核心程式碼
mcp_src = CURRENT_DIR / "taiwan-travel-mcp"
if mcp_src.exists():
    for f in mcp_src.iterdir():
        if f.is_file():
            shutil.copy(f, MCP_TARGET_DIR / f.name)
    print(f"✅ taiwan-travel-mcp 核心程式碼已部署至: {MCP_TARGET_DIR}")
else:
    print("⚠️ 找不到 taiwan-travel-mcp 資料夾，請確認安裝包完整。")

# 3.1 部署 Antigravity 工具規格檔 (.json schemas)
agy_mcp_dir = HOME / ".gemini" / "antigravity" / "mcp" / "taiwan-travel"
agy_mcp_dir.mkdir(parents=True, exist_ok=True)
schemas_src = CURRENT_DIR / "antigravity-schemas"
if schemas_src.exists():
    for f in schemas_src.glob("*.json"):
        shutil.copy(f, agy_mcp_dir / f.name)
    print(f"✅ Antigravity 工具規格檔已部署至: {agy_mcp_dir}")

# 4. 部署全域命令列工具 (travel-cli)
cli_src = CURRENT_DIR / "travel-cli"
cli_target = BIN_DIR / "travel-cli"
if cli_src.exists():
    shutil.copy(cli_src, cli_target)
    os.chmod(cli_target, 0o755)
    print(f"✅ travel-cli 指令已安裝至: {cli_target}")

# 5. 確保必要之 npm 套件存在
mcp_root = HOME / ".gemini" / "antigravity" / "mcp"
mcp_root.mkdir(parents=True, exist_ok=True)
if not (mcp_root / "node_modules" / "@modelcontextprotocol" / "sdk").exists():
    print("📦 正在安裝必要之 MCP SDK 套件...")
    os.system(f"npm install --prefix {mcp_root} @modelcontextprotocol/sdk @modelcontextprotocol/server-google-maps @duffel/api")

# 5.1 部署 Google Maps Routes API 補丁 (若有)
GMAPS_JS = str(mcp_root / "node_modules" / "@modelcontextprotocol" / "server-google-maps" / "dist" / "index.js")
gmaps_patch = CURRENT_DIR / "google-maps-patch" / "index.js"
if gmaps_patch.exists() and Path(GMAPS_JS).parent.exists():
    shutil.copy(gmaps_patch, GMAPS_JS)
    print(f"✅ Google Maps Routes API 補丁已部署至: {GMAPS_JS}")

TRAVEL_JS = str(MCP_TARGET_DIR / "index.js")

# 6. 自動注入至本機各大 AI Agent
print("\n🤖 正在自動配置各 AI Agent 環境...")

# A. Google Antigravity
agy_cfg = CONFIG_DIR / "mcp_config.json"
if not agy_cfg.exists():
    agy_cfg = HOME / ".gemini" / "antigravity" / "mcp_config.json"
if agy_cfg.exists():
    try:
        with open(agy_cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
        s = d.setdefault("mcpServers", {})
        s["taiwan-travel"] = {"command": "node", "args": [TRAVEL_JS]}
        with open(agy_cfg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("  ✅ Google Antigravity: 配置完成")
    except Exception as e:
        print("  ⚠️ Antigravity 配置提示:", e)

# B. Claude Code
claude_cfg = HOME / ".claude.json"
if claude_cfg.exists():
    try:
        with open(claude_cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
        s = d.setdefault("mcpServers", {})
        s["taiwan-travel"] = {"type": "stdio", "command": NODE_PATH, "args": [TRAVEL_JS]}
        with open(claude_cfg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("  ✅ Claude Code: 配置完成")
    except Exception as e:
        print("  ⚠️ Claude Code 配置提示:", e)

# C. OpenCode
opencode_cfg = HOME / ".config" / "opencode" / "opencode.jsonc"
if opencode_cfg.exists():
    try:
        with open(opencode_cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
        s = d.setdefault("mcp", {}).setdefault("servers", {})
        s["taiwan-travel"] = {"type": "local", "command": [NODE_PATH, TRAVEL_JS]}
        with open(opencode_cfg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("  ✅ OpenCode: 配置完成")
    except Exception as e:
        print("  ⚠️ OpenCode 配置提示:", e)

# D. Codex
codex_cfg = HOME / ".codex" / "config.toml"
if codex_cfg.exists():
    try:
        with open(codex_cfg, "r", encoding="utf-8") as f:
            c = f.read()
        if "[mcp_servers.taiwan_travel]" not in c:
            c += f'\n[mcp_servers.taiwan_travel]\ncommand = "{NODE_PATH}"\nargs = ["{TRAVEL_JS}"]\n'
            with open(codex_cfg, "w", encoding="utf-8") as f:
                f.write(c)
        print("  ✅ Codex: 配置完成")
    except Exception as e:
        print("  ⚠️ Codex 配置提示:", e)

# E. Hermes
hermes_cfg = HOME / ".hermes" / "config.yaml"
if hermes_cfg.exists():
    try:
        with open(hermes_cfg, "r", encoding="utf-8") as f:
            c = f.read()
        if "taiwan-travel" not in c and "mcp_servers:" in c:
            block = f"""  taiwan-travel:
    command: {NODE_PATH}
    args:
      - {TRAVEL_JS}
"""
            c = c.replace("mcp_servers:\n", "mcp_servers:\n" + block)
            with open(hermes_cfg, "w", encoding="utf-8") as f:
                f.write(c)
        print("  ✅ Hermes: 配置完成")
    except Exception as e:
        print("  ⚠️ Hermes 配置提示:", e)

# F. Cursor
cursor_candidates = [
    HOME / "Library" / "Application Support" / "Cursor" / "User" / "mcp.json",
    HOME / ".cursor" / "mcp.json"
]
for c_cfg in cursor_candidates:
    if c_cfg.parent.exists():
        try:
            d = {}
            if c_cfg.exists():
                with open(c_cfg, "r", encoding="utf-8") as f:
                    d = json.load(f)
            s = d.setdefault("mcpServers", {})
            s["taiwan-travel"] = {"command": NODE_PATH, "args": [TRAVEL_JS]}
            with open(c_cfg, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2)
            print(f"  ✅ Cursor: 配置完成 ({c_cfg.name})")
            break
        except Exception as e:
            print("  ⚠️ Cursor 配置提示:", e)

print("\n==================================================================")
print("🎉 恭喜老師！核心工具已成功注入您的 AI Agent！")
print("==================================================================")
print("💡 接下來如何取得各項免費金鑰？")
print("   請參考同資料夾內的教學指南手冊：")
print("   📖 TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md")
print("\n🗣️ 最聰明的懶人做法：")
print("   直接在您的 AI Agent 對話框貼上以下這句話：")
print('   「請讀取 TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md，')
print('     啟動保姆模式，一步一步帶我申請與開通免費 API 金鑰！」')
print("   AI 就會給您專屬註冊網址，並幫您自動存檔完成！")
print("==================================================================\n")
