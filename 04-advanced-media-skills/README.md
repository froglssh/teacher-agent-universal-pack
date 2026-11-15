# 🎬 老師專屬進階影音多媒體包（HyperFrames & Media-Use）

本進階包專為**想進一步製作高品質教學短影音、動態圖表動畫、社群宣傳影片、或需要免費配樂/配音/音效素材庫**的老師設計！

---

## 📦 包含的 11 套進階技能

1. **`hyperframes`**：影音與動態動畫總控入口（生成、編輯、渲染短片、Remotion 轉譯）。
2. **`hyperframes-cli`**：命令列生命週期管理（專案初始化、預覽、渲染）。
3. **`hyperframes-registry`**：400+ 個官方預製特效與動態元件市集（圖表動畫、彩帶、光暈、終端機黑底綠字等）。
4. **`hyperframes-core`**：時間軸合約與 HTML 動畫架構。
5. **`hyperframes-animation`**：動畫物理曲線與運動特效控制。
6. **`hyperframes-audio`**：音效、背景音樂混音與淡入淡出。
7. **`hyperframes-studio`**：Studio 視覺化播放器與專案即時預覽。
8. **`hyperframes-creative`**：創意設計指南、風格調色與排版規範。
9. **`hyperframes-keyframes`**：關鍵影格與鏡頭運鏡（縮放、平移等）。
10. **`media-use`**：HeyGen 免費曲庫 (10k+ 首)、音效、語音旁白 (TTS)、向量 Logo 與去背處理。
11. **`remotion-to-hyperframes`**：React Remotion 影片專案轉譯器。

---

## ⚙️ 系統環境需求（前置作業）

由於影片渲染涉及網頁即時合成與視訊編碼，請確認電腦已具備以下兩項免費工具：
1. **Node.js (v22 以上)**：
   - 請至 [Node.js 官方網站](https://nodejs.org) 下載 LTS 或最新版本安裝。
2. **FFmpeg**：
   - **macOS**：打開終端機執行 `brew install ffmpeg`。
   - **Windows**：可使用 `winget install Gyan.FFmpeg` 或透過套件管理工具安裝。

---

## 🚀 一鍵安裝步驟

### 方法一：讓 Agent 為你自動安裝
下載本資料夾後，直接在對話框中對你的 AI Agent（Antigravity、Claude Code、Codex、OpenCode 或 Hermes）說：
> 「**請幫我執行 install_media_skills.py，安裝進階影音多媒體包。**」

### 方法二：在終端機手動執行
打開終端機（Terminal / PowerShell），切換至本資料夾並執行：
```bash
python3 install_media_skills.py
```

---

## 💡 安裝後如何使用？

安裝完成後，你可以直接用自然語言對 Agent 下達指令：
- 「**我想做一段 15 秒的『光合作用光反應』重點教學短片，請用 HyperFrames 規劃時間軸並製作。**」
- 「**請幫我用 media-use 找一首適合科普演講開場的輕快背景音樂。**」
- 「**幫我從 hyperframes-registry 加入折線圖成長動畫組件。**」
- 「**幫我啟動 HyperFrames Studio 預覽畫面。**」
