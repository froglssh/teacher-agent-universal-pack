# 老師專用 AI Agent 核心工具箱與技能庫目錄

歡迎使用！本專案專為臺灣各級學校教師量身打造，模組化分類為 **四大核心模組** 與 **開箱即用線上指引**，讓您與 AI Agent 能一目了然、精準取用所需資源。

> 🌐 **線上公開指引網址（直接分享給老師）**：[https://froglssh.github.io/teacher-agent-universal-pack/](https://froglssh.github.io/teacher-agent-universal-pack/)  
> 📥 **下載 PDF 重點大字版手冊（A4 5頁列印檔）**：[點此下載手冊 PDF](./老師專屬_AI_Agent_全能工具箱安裝與使用指南_重點大字版.pdf)  
> 📦 **GitHub 專案原始碼與安裝包**：[https://github.com/froglssh/teacher-agent-universal-pack](https://github.com/froglssh/teacher-agent-universal-pack)

**支援的 AI Agent**：Google Antigravity、Claude Code、Codex、OpenCode、Cursor、Hermes。  
所有內容皆為公開可分享版本，**不含任何個人知識庫、私人雲端路徑、帳號密碼或學生個資**。

---

## 📂 四大核心模組目錄導覽

```
skill/
├── 📁 01-teacher-skills/          # 模組一：教師教學、科研與行政專用 30 大 Skills 技能包
├── 📁 02-universal-mcps/          # 模組二：跨 Agent 通用 MCP 伺服器與 Google 生態系 API 部署
├── 📁 03-travel-and-transit/      # 模組三：交通、國際航班、外幣匯率與即時氣象工具箱
└── 📁 04-advanced-media-skills/   # 模組四：老師專用進階影音多媒體包（選配：代碼化短片製作與免費曲庫）
```

---

### 1. 🎓 [01-teacher-skills/](./01-teacher-skills/)（教師教學專用技能包）
專為高中、各級學校教師與行政同仁量身打造的專屬 Agent 技能：
* 📦 **`public-teacher-skills/`**：**30 大精選教學技能原始檔案**（新增包含：蘇格拉底引導教學 `teach`、文獻引用防偽 `citation-management`、科學報告嚴謹審核 `scientific-writing`、Nature 論文結構 `nature-writing`、精準潤稿 `nature-polishing`、決策質詢 `grill-me` 以及技能市集探索 `find-skills`）。
* 🗜️ **`public-teacher-skills.zip`**：[點此一鍵下載基礎技能包](./public-teacher-skills.zip)（滑鼠雙擊解壓即可讓 Agent 一秒導入）。
* 📑 **`TEACHER_AGENT_RECOMMENDED_STACK.md`**：導師與各科任課教師 AI 工具與技能推薦架構圖。

---

### 2. ⚙️ [02-universal-mcps/](./02-universal-mcps/)（跨 Agent 通用 MCP 與 Google API 生態）
提供 Google Antigravity、Claude Code、Codex、OpenCode 與 Cursor 通用的外接 MCP 工具與 Google API 快速配置方案：
* 📖 **`UNIVERSAL_AGENT_MCP_INSTALLER.md`**：完整跨平台通用 MCP 安裝指引手冊（含 Notion、Padlet、Canva、Playwright、GitHub 與 Office 處理）。
* 🐍 **`install_universal_mcps.py`**：一鍵全自動跨 Agent MCP 安裝與配置腳本。
* 📝 **`GOOGLE_API_STEP_BY_STEP_GUIDE.md`**：老師專屬「保姆級」Google API（Drive 秒搜、Classroom、People 通訊錄、日曆）開通指南。
* 📊 **`installed_mcps_tools_and_runtimes_inventory.md`**：本機執行環境、已安裝 MCP 伺服器與外掛模組全盤點報告。

---

### 3. ✈️ [03-travel-and-transit/](./03-travel-and-transit/)（旅行、交通、航班與金融氣象）
整合校外教學、戶外實察通勤即時路況、國際機票與匯率外幣的完整多 Agent 工具套裝：
* 📘 **`TRAVEL_AND_LIFE_API_STEP_BY_STEP_GUIDE.md`**：生活、公車高鐵、機票比價與外幣匯率「保姆級」申請指引手冊（零私密金鑰，100% 乾淨開源安全版）。
* 🐍 **`install_travel_suite.py`**：生活與交通工具箱純淨一鍵安裝器（自動部署代碼至各大 Agent）。
* ⚙️ **`travel_transit_config_template.json`**：空白憑證範本。

---

### 4. 🎬 [04-advanced-media-skills/](./04-advanced-media-skills/)（老師專用進階影音多媒體包・選配）
專為有教學短影片、動態宣傳與多媒體動畫創作需求的老師設計：
* 📦 **`skills/`**：收錄 **HyperFrames 完整 11 套影音技能**（`hyperframes`, `hyperframes-cli`, `hyperframes-registry` 400+ 元件庫, `media-use` 10k+ 免費曲庫與 TTS 配音, `remotion-to-hyperframes` 等）。
* 🗜️ **`04-advanced-media-skills.zip`**：[點此一鍵下載多媒體技能包](./04-advanced-media-skills.zip)（內含環境檢測腳本）。
* 🐍 **`install_media_skills.py`**：全自動環境檢查（Node.js 22+、FFmpeg）與一鍵部署腳本。
* 📖 **`README.md`**：完整多媒體安裝與教學指令示範。

---

## 💡 老師免終端機快速使用原則

所有的子目錄手冊都採用「對 Agent 說一句話自動完成」的設計：

1. **想裝教學技能（模組一）**：對 Agent 說 `請讀取 01-teacher-skills/，幫我安裝教學技能`。
2. **想裝 Google 與通用 MCP（模組二）**：對 Agent 說 `請讀取 02-universal-mcps/UNIVERSAL_AGENT_MCP_INSTALLER.md 幫我安裝`。
3. **想裝交通航班工具箱（模組三）**：對 Agent 說 `請讀取 03-travel-and-transit/，執行 install_travel_suite.py 幫我安裝`。
4. **想裝進階影音多媒體包（模組四）**：對 Agent 說 `請讀取 04-advanced-media-skills/，執行 install_media_skills.py 幫我安裝`。

---

製作與維護：林獻升 老師  
授權：MIT 開源共享協議（歡迎全臺灣教育夥伴自由轉載與教學使用）
