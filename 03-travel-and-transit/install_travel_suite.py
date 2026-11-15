#!/usr/bin/env python3
"""
老師專用：生活、交通、航班與匯率工具箱一鍵安裝器 (純淨開源版)
功能：
1. 自動部署 taiwan-travel-mcp 伺服器與 travel-cli 指令
2. 自動建立空白設定檔 ~/.gemini/config/travel_transit_config.json
3. 自動偵測本機各大 Agent (Antigravity, Claude Code, Codex, OpenCode, Hermes) 並注入配置
4. 提醒老師依照 TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md 填入自己申請的免費金鑰
"""
import os
import sys
import json
import shutil
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
HOME = Path.home()
NODE_PATH = shutil.which("node") or "/usr/local/bin/node"

print("======================================================")
print("🎒 老師專用：生活、交通、機票比價與匯率工具箱安裝器")
print("======================================================")

# 1. 建立目錄
CONFIG_DIR = HOME / ".gemini" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
MCP_TARGET_DIR = HOME / ".gemini" / "antigravity" / "mcp" / "taiwan-travel-mcp"
MCP_TARGET_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR = HOME / ".local" / "bin"
BIN_DIR.mkdir(parents=True, exist_ok=True)

# 2. 建立設定檔 (若已存在則不覆蓋，若不存在則建立空白範本)
cfg_target = CONFIG_DIR / "travel_transit_config.json"
if not cfg_target.exists():
    cfg_data = {
        "tdx": {
            "clientId": "",
            "clientSecret": "",
        },
        "exchangeRateApiKey": "",
        "duffelApiKey": "",
    }
    with open(cfg_target, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
    print(f"✅ 已建立空白憑證設定檔: {cfg_target}")
else:
    print(f"ℹ️ 設定檔已存在，保留現有設定: {cfg_target}")

# 3. 部署 taiwan-travel-mcp 伺服器代碼
mcp_src = CURRENT_DIR / "taiwan-travel-mcp"
if mcp_src.exists():
    for f in mcp_src.iterdir():
        if f.is_file():
            shutil.copy(f, MCP_TARGET_DIR / f.name)
    print(f"✅ taiwan-travel-mcp 核心程式碼已部署至: {MCP_TARGET_DIR}")
else:
    print("⚠️ 找不到 taiwan-travel-mcp 資料夾，請確認安裝包完整。")

# 4. 部署全域命令列工具 (travel-cli)
cli_src = CURRENT_DIR / "travel-cli"
cli_target = BIN_DIR / "travel-cli"
if cli_src.exists():
    shutil.copy(cli_src, cli_target)
    os.chmod(cli_target, 0o755)
    print(f"✅ travel-cli 指令已安裝至: {cli_target}")

# 5. 確保套件存在
mcp_root = HOME / ".gemini" / "antigravity" / "mcp"
mcp_root.mkdir(parents=True, exist_ok=True)
if not (mcp_root / "node_modules" / "@modelcontextprotocol" / "sdk").exists():
    print("📦 正在安裝必要之 MCP SDK 套件...")
    os.system(f"npm install --prefix {mcp_root} @modelcontextprotocol/sdk @modelcontextprotocol/server-google-maps")

TRAVEL_JS = str(MCP_TARGET_DIR / "index.js")

# 6. 跨 Agent 注入配置
# A. Google Antigravity
agy_cfg = CONFIG_DIR / "mcp_config.json"
if agy_cfg.exists():
    try:
        with open(agy_cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
        s = d.setdefault("mcpServers", {})
        s["taiwan-travel"] = {"command": "node", "args": [TRAVEL_JS]}
        with open(agy_cfg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("✅ 已成功注入: Google Antigravity")
    except Exception as e:
        print("⚠️ Antigravity 注入提示:", e)

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
        print("✅ 已成功注入: Claude Code")
    except Exception as e:
        print("⚠️ Claude Code 注入提示:", e)

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
        print("✅ 已成功注入: OpenCode")
    except Exception as e:
        print("⚠️ OpenCode 注入提示:", e)

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
            print("✅ 已成功注入: Codex")
        else:
            print("ℹ️ Codex 已有 taiwan_travel")
    except Exception as e:
        print("⚠️ Codex 注入提示:", e)

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
            print("✅ 已成功注入: Hermes")
        else:
            print("ℹ️ Hermes 已有 taiwan-travel")
    except Exception as e:
        print("⚠️ Hermes 注入提示:", e)

print("======================================================")
print("🎉 基礎工具箱安裝完成！")
print("💡 溫馨提醒：")
print("1. 即時外幣匯率與天氣已開箱即用！")
print("2. 交通（TDX）與機票（Duffel）請參閱 TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md")
print("   自行到官網免費註冊取得金鑰，並直接貼給 Agent 即可自動存入！")
print("======================================================")
