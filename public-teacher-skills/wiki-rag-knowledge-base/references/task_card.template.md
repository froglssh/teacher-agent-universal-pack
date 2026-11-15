---
task_id: "task-YYYYMMDD-001"
title: "任務簡述（例如：匯入 114 學年度高中生物選修教材）"
role: "Builder | Ingestor | Librarian | Maintainer | Optimizer"
owner: null
locked_at: null
status: "pending | in_progress | needs_review | done"
created_at: "YYYY-MM-DDTHH:MM:SSZ"
needs_review: false
---

## 一、任務目標與情境描述
- 詳細說明本卡片需要執行的核心任務內容與預期成果。

## 二、輸入檔案與參考來源
- 原始檔案路徑：`inbox/xxx.pdf` 或 `raw/xxx.docx`
- 參考設定檔：`kb.config.yaml`
- 關聯 Wiki 頁面：`wiki/concepts/xxx.md`

## 三、預期交付產出
- [ ] 物理清洗與語意清洗成果存入 `clean/`
- [ ] 結構切塊存入 `chunks/<source_id>.jsonl`
- [ ] 執行 `kb index` 更新索引資料庫
- [ ] 編譯/更新對應之 `wiki/sources/` 與 `wiki/concepts/` 專頁
- [ ] 通過 `kb lint` 檢查並無斷鏈切塊

## 四、完工查核與交接紀錄 (Agent Sign-off)
- **執行 Agent**：
- **完工時間**：
- **Git Commit 雜湊**：
- **備註或發現之知識矛盾**：
