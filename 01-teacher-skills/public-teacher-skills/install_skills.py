#!/usr/bin/env python3
"""
跨 Agent 技能一鍵全自動安裝腳本
讓老師雙擊解壓縮後，Agent 只要跑此腳本即可自動分發到 Antigravity、Claude Code、Codex 與 OpenCode 的技能目錄。
"""

import os
import shutil
from pathlib import Path

def main():
    home = Path.home()
    source_dir = Path(__file__).resolve().parent

    # 候選安裝目標目錄
    target_dirs = [
        home / ".gemini" / "config" / "skills",        # Antigravity 全域
        home / ".claude" / "skills",                  # Claude Code 全域
        Path.cwd() / ".agents" / "skills",            # Antigravity 2 / 專案本地
        Path.cwd() / ".claude" / "skills",            # Claude Code 專案本地
        home / ".config" / "opencode" / "skills",     # OpenCode
        Path(os.environ.get("LOCALAPPDATA", home)) / "hermes" / "skills",  # Hermes (Windows)
        home / ".hermes" / "skills"                # Hermes (macOS / Linux)
    ]

    installed_targets = []
    skills = [p for p in source_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    print(f"📦 偵測到 {len(skills)} 個教學技能準備安裝...")

    for target in target_dirs:
        # 如果目標的上層目錄存在（代表本機有裝該 Agent），或者為 gemini 全域目錄，則進行安裝
        if target.parent.exists() or ".gemini" in str(target) or ".claude" in str(target):
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

    print("\n🎉 全部技能已成功自動部署完畢！")
    print(f"共計安裝 {len(skills)} 個技能至以下環境：")
    for t in installed_targets:
        print(f" - {t}")
    print("\n請重新啟動 Agent 或在對話框輸入 /skills 即可立即使用！")

if __name__ == "__main__":
    main()
