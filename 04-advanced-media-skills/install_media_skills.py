#!/usr/bin/env python3
"""
🎬 老師專屬「進階影音多媒體包」一鍵安裝腳本
支援跨 Agent (Antigravity, Claude Code, Codex, OpenCode, Hermes)
自動檢查 Node.js 與 FFmpeg 環境，並安裝 HyperFrames 影音動畫全套技能！
"""

import os
import shutil
import subprocess
from pathlib import Path

def check_env():
    print("🔍 正在檢驗多媒體執行環境需求...")
    # Check node
    node = shutil.which("node")
    ffmpeg = shutil.which("ffmpeg")

    if not node:
        print("⚠️ 未檢測到 Node.js！HyperFrames 需要 Node.js (v22 以上)。建議前往 https://nodejs.org 安裝。")
    else:
        try:
            ver = subprocess.check_output(["node", "-v"], text=True).strip()
            print(f"✅ Node.js 檢測正常: {ver}")
        except:
            pass

    if not ffmpeg:
        print("⚠️ 未檢測到 FFmpeg！影片導出與音訊編碼需要 FFmpeg。建議 macOS 執行 'brew install ffmpeg'。")
    else:
        print("✅ FFmpeg 檢測正常")

def main():
    home = Path.home()
    source_dir = Path(__file__).resolve().parent / "skills"

    if not source_dir.exists():
        print(f"❌ 找不到技能來源資料夾: {source_dir}")
        return

    check_env()
    print("-" * 50)

    # 候選安裝目標目錄
    target_dirs = [
        home / ".gemini" / "config" / "skills",        # Antigravity 全域
        home / ".claude" / "skills",                  # Claude Code 全域
        home / ".codex" / "skills",                   # Codex 全域
        home / ".agents" / "skills",                  # OpenCode / Agents 全域
        Path.cwd() / ".agents" / "skills",            # 專案本地
        Path.cwd() / ".claude" / "skills",            # Claude Code 專案本地
        home / ".config" / "opencode" / "skills",     # OpenCode 專屬
        Path(os.environ.get("LOCALAPPDATA", home)) / "hermes" / "skills",  # Hermes (Windows)
        home / ".hermes" / "skills"                # Hermes (macOS / Linux)
    ]

    installed_targets = []
    skills = [p for p in source_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    print(f"📦 準備安裝 {len(skills)} 個進階影音多媒體技能...")

    for target in target_dirs:
        if target.parent.exists() or ".gemini" in str(target) or ".claude" in str(target) or ".agents" in str(target):
            try:
                target.mkdir(parents=True, exist_ok=True)
                for s in skills:
                    dest = target / s.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(s, dest)
                installed_targets.append(str(target))
                print(f"✅ 成功安裝到: {target}")
            except Exception as e:
                print(f"⚠️ 安裝到 {target} 失敗: {e}")

    print("\n🎉「進階影音多媒體包」全部安裝完畢！")
    print(f"共計安裝 {len(skills)} 個技能至以下環境：")
    for t in installed_targets:
        print(f" - {t}")
    print("\n您可以直接對 Agent 下達指令：")
    print("👉「幫我用 HyperFrames 做一段 15 秒教學重點影片」")
    print("👉「幫我用 media-use 為這段簡報尋找免費背景音樂與音效」")

if __name__ == "__main__":
    main()
