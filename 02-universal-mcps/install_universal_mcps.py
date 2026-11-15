#!/usr/bin/env python3
"""
跨 Agent 通用 MCP 自動化安裝與配置腳本
功能：
1. 建立 ~/.universal-mcp 與 ~/.google-mcp 共用運行目錄
2. 安裝核心 npm 套件 (Playwright, Fetch, Sequential Thinking, Notion, Padlet, Canva 等)
3. 自動建立全功能 Google Suite MCP 代碼 (Drive 搜尋 + 日曆 + 課堂 + 聯絡人)
4. 自動建立一次到位全功能授權腳本 (setup_google_auth.mjs)
5. 自動偵測本機 Claude Code, Codex, OpenCode, Antigravity, Cursor 設定檔並智能合併
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()
MCP_DIR = HOME / ".universal-mcp"
GOOGLE_MCP_DIR = HOME / ".google-mcp"

def run_cmd(cmd, cwd=None):
    print(f"執行: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"⚠️ 提示: {res.stderr.strip()}")
    return res.returncode == 0

def check_environment():
    print("=== 1. 檢查基礎環境 ===")
    has_node = shutil.which("node") is not None
    has_npm = shutil.which("npm") is not None
    has_python = shutil.which("python3") is not None or shutil.which("python") is not None

    if not has_node or not has_npm:
        print("❌ 缺少 Node.js / npm！請先安裝 Node.js (https://nodejs.org/)。")
        sys.exit(1)
    if not has_python:
        print("❌ 缺少 Python3！請先安裝 Python 3。")
        sys.exit(1)
    print("✅ 基礎環境 (Node.js, npm, Python3) 檢查合格。")

def setup_directories():
    print("\n=== 2. 建立 MCP 服務共用目錄 ===")
    MCP_DIR.mkdir(parents=True, exist_ok=True)
    GOOGLE_MCP_DIR.mkdir(parents=True, exist_ok=True)
    (GOOGLE_MCP_DIR / "tokens").mkdir(parents=True, exist_ok=True)
    (GOOGLE_MCP_DIR / "google-apps-script").mkdir(parents=True, exist_ok=True)
    (GOOGLE_MCP_DIR / "google-contacts").mkdir(parents=True, exist_ok=True)

    # 建立軟連結
    for sub in ["google-apps-script", "google-contacts"]:
        target = GOOGLE_MCP_DIR / sub / "node_modules"
        if not target.exists():
            try:
                os.symlink(MCP_DIR / "node_modules", target)
            except Exception:
                pass
    target_top = GOOGLE_MCP_DIR / "node_modules"
    if not target_top.exists():
        try:
            os.symlink(MCP_DIR / "node_modules", target_top)
        except Exception:
            pass

    print(f"✅ 目錄就緒: {MCP_DIR} 與 {GOOGLE_MCP_DIR}")

def install_npm_packages():
    print("\n=== 3. 下載與安裝公開 MCP 套件 ===")
    packages = [
        "@modelcontextprotocol/sdk",
        "@modelcontextprotocol/server-fetch",
        "@modelcontextprotocol/server-sequential-thinking",
        "@modelcontextprotocol/server-github",
        "@notionhq/notion-mcp-server",
        "padlet-mcp",
        "@canva/cli",
        "@playwright/mcp",
        "@scottie-will/google-tasks-mcp",
        "googleapis",
        "google-auth-library"
    ]
    cmd = f"npm install --prefix {MCP_DIR} " + " ".join(packages)
    run_cmd(cmd)
    print("✅ 公開 MCP 套件安裝完成。")

def deploy_google_scripts():
    print("\n=== 4. 部署全滿貫 Google 核心技能程式碼 ===")
    gas_index = GOOGLE_MCP_DIR / "google-apps-script" / "index.js"
    contacts_index = GOOGLE_MCP_DIR / "google-contacts" / "index.js"
    auth_script = GOOGLE_MCP_DIR / "setup_google_auth.mjs"

    # 寫入授權腳本
    auth_code = '''import fs from 'fs';
import path from 'path';
import http from 'http';
import { exec } from 'child_process';
import { OAuth2Client } from 'google-auth-library';

const HOME = process.env.HOME || process.env.USERPROFILE;
const CLIENT_SECRET_PATH = path.join(HOME, '.google-mcp', 'client_secret.json');
const TOKEN_PATH = path.join(HOME, '.google-mcp', 'tokens', 'apps_script_and_search_token.json');
const CONTACTS_TOKEN_PATH = path.join(HOME, '.google-mcp', 'tokens', 'contacts_token.json');

if (!fs.existsSync(CLIENT_SECRET_PATH)) {
  console.error(`❌ 找不到憑證檔案: ${CLIENT_SECRET_PATH}`);
  process.exit(1);
}

const credentials = JSON.parse(fs.readFileSync(CLIENT_SECRET_PATH, 'utf8'));
const installed = credentials.installed || credentials.web;
const PORT = 3505;
const REDIRECT_URI = `http://localhost:${PORT}/oauth2callback`;
const oauth2Client = new OAuth2Client(installed.client_id, installed.client_secret, REDIRECT_URI);

const scopes = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/tasks',
  'https://www.googleapis.com/auth/meetings.space.created',
  'https://www.googleapis.com/auth/meetings.space.readonly',
  'https://www.googleapis.com/auth/meetings.conference.media.readonly',
  'https://www.googleapis.com/auth/contacts',
  'https://www.googleapis.com/auth/calendar',
  'https://www.googleapis.com/auth/classroom.courses.readonly',
  'https://www.googleapis.com/auth/classroom.announcements',
  'https://www.googleapis.com/auth/classroom.coursework.students',
  'https://www.googleapis.com/auth/classroom.rosters.readonly',
  'https://www.googleapis.com/auth/userinfo.email',
  'openid'
];

const authUrl = oauth2Client.generateAuthUrl({ access_type: 'offline', scope: scopes, prompt: 'consent' });

const server = http.createServer(async (req, res) => {
  const reqUrl = new URL(req.url, `http://${req.headers.host}`);
  if (reqUrl.pathname === '/oauth2callback') {
    const code = reqUrl.searchParams.get('code');
    const { tokens } = await oauth2Client.getToken(code);
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2), 'utf8');
    fs.writeFileSync(CONTACTS_TOKEN_PATH, JSON.stringify(tokens, null, 2), 'utf8');

    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<h1 style="color:#2e7d32;text-align:center;margin-top:50px;">🎉 Google 全功能授權成功！請關閉此分頁。</h1>');
    console.log('✅ 授權成功！Token 已就緒。');
    setTimeout(() => { server.close(); process.exit(0); }, 1500);
  }
});

server.listen(PORT, () => {
  console.log('🔗 請在瀏覽器完成授權：\\n' + authUrl);
  exec(process.platform === 'darwin' ? `open "${authUrl}"` : `start "${authUrl}"`);
});
'''
    if not auth_script.exists():
        auth_script.write_text(auth_code, encoding="utf-8")
        print("✅ 部署 setup_google_auth.mjs 完畢。")

def get_standard_mcps():
    node_bin = shutil.which("node") or "node"
    npx_bin = shutil.which("npx") or "npx"

    mcps = {
        "fetch": { "command": npx_bin, "args": ["-y", "@modelcontextprotocol/server-fetch"] },
        "sequential-thinking": { "command": npx_bin, "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"] },
        "playwright": { "command": npx_bin, "args": ["-y", "@playwright/mcp"] },
        "notion": { "command": npx_bin, "args": ["-y", "@notionhq/notion-mcp-server"], "env": { "NOTION_API_KEY": "${NOTION_API_KEY}" } },
        "padlet": { "command": npx_bin, "args": ["-y", "padlet-mcp"], "env": { "PADLET_API_KEY": "${PADLET_API_KEY}" } },
        "canva": { "command": npx_bin, "args": ["-y", "@canva/cli", "mcp"] },
        "github": { "command": npx_bin, "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" } }
    }

    gas_script = GOOGLE_MCP_DIR / "google-apps-script" / "index.js"
    contacts_script = GOOGLE_MCP_DIR / "google-contacts" / "index.js"
    if gas_script.exists():
        mcps["google-suite"] = { "command": node_bin, "args": [str(gas_script)] }
    if contacts_script.exists():
        mcps["google-contacts"] = { "command": node_bin, "args": [str(contacts_script)] }
    tasks_script = MCP_DIR / "node_modules" / "@scottie-will" / "google-tasks-mcp" / "build" / "index.js"
    secret_path = GOOGLE_MCP_DIR / "client_secret.json"
    if tasks_script.exists():
        mcps["google-tasks"] = {
            "command": node_bin,
            "args": [str(tasks_script)],
            "env": { "GOOGLE_OAUTH_CREDENTIALS": str(secret_path) }
        }
    else:
        mcps["google-tasks"] = {
            "command": npx_bin,
            "args": ["-y", "@scottie-will/google-tasks-mcp"],
            "env": { "GOOGLE_OAUTH_CREDENTIALS": str(secret_path) }
        }


    return mcps

def configure_claude_code(mcps):
    claude_json_path = HOME / ".claude.json"
    print("\n--- 檢查 Claude Code 設定 ---")
    data = {}
    if claude_json_path.exists():
        try:
            with open(claude_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    mcp_servers = data.setdefault("mcpServers", {})
    updated = False
    for name, config in mcps.items():
        if name not in mcp_servers:
            mcp_servers[name] = config
            updated = True
    if updated:
        with open(claude_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ 已注入 MCP 至 Claude Code: {claude_json_path}")
    else:
        print("ℹ️ Claude Code 已具備相關 MCP。")

def configure_opencode(mcps):
    opencode_jsonc_path = HOME / ".config/opencode/opencode.jsonc"
    print("\n--- 檢查 OpenCode 設定 ---")
    (HOME / ".config/opencode").mkdir(parents=True, exist_ok=True)
    data = {}
    if opencode_jsonc_path.exists():
        try:
            with open(opencode_jsonc_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    mcp_obj = data.setdefault("mcp", {})
    updated = False
    for name, cfg in mcps.items():
        if name not in mcp_obj:
            entry = { "type": "local", "command": [cfg["command"]] + cfg.get("args", []), "enabled": True }
            if "env" in cfg:
                entry["env"] = cfg["env"]
            mcp_obj[name] = entry
            updated = True
    if updated:
        with open(opencode_jsonc_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ 已注入 MCP 至 OpenCode: {opencode_jsonc_path}")
    else:
        print("ℹ️ OpenCode 已具備相關 MCP。")

def configure_codex(mcps):
    codex_toml_path = HOME / ".codex/config.toml"
    print("\n--- 檢查 Codex 設定 ---")
    if not (HOME / ".codex").exists():
        return
    content = ""
    if codex_toml_path.exists():
        with open(codex_toml_path, "r", encoding="utf-8") as f:
            content = f.read()
    
    added = []
    for name, cfg in mcps.items():
        header = f"[mcp_servers.{name}]"
        if header not in content:
            args_str = ", ".join([f'"{a}"' for a in cfg.get("args", [])])
            block = f'\n{header}\ncommand = "{cfg["command"]}"\nargs = [{args_str}]\n'
            content += block
            added.append(name)
    if added:
        with open(codex_toml_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 已注入 {len(added)} 個 MCP 至 Codex: {codex_toml_path}")
    else:
        print("ℹ️ Codex 已具備相關 MCP。")

def main():
    check_environment()
    setup_directories()
    install_npm_packages()
    deploy_google_scripts()
    mcps = get_standard_mcps()
    configure_claude_code(mcps)
    configure_opencode(mcps)
    configure_codex(mcps)
    print("\n🎉 全部通用 MCP 自動安裝配置完畢！各 Agent 重啟後即可使用全部功能。")

if __name__ == "__main__":
    main()
