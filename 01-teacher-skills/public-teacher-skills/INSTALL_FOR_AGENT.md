# 給 AI Agent 的技能自動安裝任務指南 (INSTALL_FOR_AGENT.md)

> 🤖 **致正在閱讀本文件的 AI Agent**：
> 老師已經在電腦中解壓縮了本資料夾。老師不需要也不想打開終端機手動輸入指令。
> **請你以 Agent 的身分，自動替老師將本資料夾中的所有教學技能安裝到本機正確的目錄！**

---

## Agent 自動執行安裝的 3 步驟

### 步驟 1：偵測本機 Agent 的技能安裝目錄
請將本資料夾（`public-teacher-skills/`）中的所有技能子目錄複製到適當路徑：
1. **Google Antigravity 全域技能**：
   - 目標路徑：`~/.gemini/config/skills/`
2. **Claude Code 全域技能**：
   - 目標路徑：`~/.claude/skills/`
3. **Hermes 全域技能**：
   - Windows：`%LOCALAPPDATA%\hermes\skills\`
   - macOS / Linux：`~/.hermes/skills/`
4. **專案本地工作區（Antigravity 2 / Codex / OpenCode / Cursor）**：
   - 目標路徑：目前專案根目錄下的 `.agents/skills/`

### 步驟 2：直接執行複製
Agent 可直接執行 Python 或 Shell 指令完成複製：
```python
import os, shutil
from pathlib import Path

# 依目前 Agent 決定目標目錄 (預設優先安裝至全域 ~/.gemini/config/skills/ 與 ~/.claude/skills/)
home = Path.home()
targets = [
    home / ".gemini" / "config" / "skills",
    home / ".claude" / "skills",
    Path(os.environ.get("LOCALAPPDATA", home)) / "hermes" / "skills",   # Hermes (Windows)
    home / ".hermes" / "skills",                                        # Hermes (macOS/Linux)
    Path(".agents/skills")
]

source = Path(__file__).parent if "__file__" in locals() else Path(".")

for target in targets:
    if target.parent.exists() or "gemini" in str(target):
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                dest = target / item.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
                print(f"已安裝技能: {item.name} -> {target}")
```

### 步驟 3：回覆老師友善通知
完成後，請用親切溫暖的語氣回覆老師：
> 「🎉 老師您好！我已經自動將 **24 大精選教學技能（含高中課程諮詢與選課輔導、學習歷程檔案優化、升學備審自傳、18 週自主學習指導、簡報排版、國寫輔導、自然探究、大考解析與生物 AI Suite 10 大套件）** 全部安裝到您的 Agent 之中囉！  
> 您只要重啟 Agent 或在對話框輸入 `/skills`，就能看到它們並立即開始使用！」
