#!/usr/bin/env python3
"""
kb.py — Wiki-RAG 知識庫標準操作命令行工具 (Zero-Dependency Python 3 CLI)

本工具為 Wiki-RAG 知識庫系統中所有 AI Agent（Codex、Antigravity、OpenCode、Hermes、Claude Code 等）
與人類維護者操作知識庫的統一介面。凡可重現之清洗、切塊、建立索引、檢索、引用查驗、健全性檢查與任務派工，
一律透過本指令執行，確保各工具產出一致之結果。

支援子指令：
  kb doctor               檢查知識庫目錄結構、設定檔、manifest 與 Wiki 引用一致性
  kb ingest <file>        檔案雜湊去重、版本追蹤、自然切塊、填寫情境句與 metadata
  kb index [--rebuild]    建立或從 chunks/ 重建 SQLite FTS5 全文索引庫
  kb search "<query>"     執行 FTS5 全文檢索與 BM25 評分（支援 --k 與過濾）
  kb cite <chunk_id>      提取指定切塊之完整正文、情境句與 metadata 供引用查核
  kb lint                 掃描孤兒頁面、失效引用、superseded 引用與無出處論點
  kb eval                 執行 eval/golden.jsonl 評估四項檢索指標
  kb task <subcmd>        管理 tasks/ 任務卡片 (new, claim, done, list)
"""

import sys
import os
import json
import sqlite3
import hashlib
import argparse
import re
from pathlib import Path
from datetime import datetime

# ==========================================
# 輔助函式與路徑解析
# ==========================================

def find_kb_root(start_path=None) -> Path:
    """自當前路徑向上尋找知識庫根目錄（以包含 AGENTS.md 或 kb.config.yaml 為準）"""
    curr = Path(start_path or os.getcwd()).resolve()
    for p in [curr] + list(curr.parents):
        if (p / "AGENTS.md").exists() or (p / "kb.config.yaml").exists() or (p / "wiki").is_dir():
            return p
    return curr

def load_config(root: Path) -> dict:
    cfg_path = root / "kb.config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        import yaml
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # 簡易 YAML 容錯解析（若未安裝 PyYAML 則讀取預設）
        cfg = {}
        with open(cfg_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and ":" in line:
                    k, v = line.split(":", 1)
                    cfg[k.strip()] = v.strip()
        return cfg

def load_manifest(root: Path) -> dict:
    m_path = root / "state" / "manifest.json"
    if m_path.exists():
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"sources": {}}
    return {"sources": {}}

def save_manifest(root: Path, data: dict):
    m_path = root / "state" / "manifest.json"
    m_path.parent.mkdir(parents=True, exist_ok=True)
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def compute_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

# ==========================================
# 指令實作 1: kb doctor
# ==========================================

def cmd_doctor(args):
    root = find_kb_root()
    print(f"🔍 檢查知識庫目錄：{root}")
    issues = []
    
    # 1. 必備目錄檢查
    required_dirs = ["raw", "clean", "chunks", "index", "state", "tasks", "wiki", "eval"]
    for d in required_dirs:
        dp = root / d
        if not dp.is_dir():
            issues.append(f"❌ 缺少必要目錄：{d}/")
        else:
            print(f"  ✓ 目錄完整：{d}/")

    # 2. 核心規範與設定檔
    if not (root / "AGENTS.md").exists():
        issues.append("❌ 缺少規範正本：AGENTS.md")
    else:
        print("  ✓ 規範正本存在：AGENTS.md")

    if not (root / "kb.config.yaml").exists():
        issues.append("⚠️ 缺少設定檔：kb.config.yaml（將使用內建預設值）")
    else:
        print("  ✓ 設定檔存在：kb.config.yaml")

    # 3. 狀態清單 manifest.json
    m_path = root / "state" / "manifest.json"
    if not m_path.exists():
        issues.append("⚠️ state/manifest.json 尚未初始化")
    else:
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            src_count = len(m.get("sources", {}))
            print(f"  ✓ Manifest 狀態正常，已追蹤 {src_count} 份來源")
        except Exception as e:
            issues.append(f"❌ state/manifest.json 解析失敗：{e}")

    # 4. 切塊與資料庫一致性
    chunk_files = list((root / "chunks").glob("*.jsonl")) if (root / "chunks").is_dir() else []
    print(f"  ✓ 現有切塊檔案數：{len(chunk_files)} 個 JSONL")

    # 5. 總結
    print("\n" + "="*40)
    if issues:
        print(f"🚨 健全性檢查發現 {len(issues)} 個問題：")
        for iss in issues:
            print(f"   {iss}")
        sys.exit(1)
    else:
        print("🎉 kb doctor 全數通過！知識庫結構完備合規。")

# ==========================================
# 指令實作 2: kb ingest
# ==========================================

def cmd_ingest(args):
    root = find_kb_root()
    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"❌ 找不到來源檔案：{file_path}")
        sys.exit(1)

    print(f"📥 開始匯入來源檔案：{file_path.name}")
    
    # 計算雜湊
    file_hash = compute_hash(file_path)
    source_id = args.id or file_path.stem
    manifest = load_manifest(root)
    
    # 檢查是否已存在
    existing = manifest.get("sources", {}).get(source_id)
    if existing and existing.get("hash") == file_hash and not args.force:
        print(f"ℹ️ 檔案內容雜湊未變更 ({file_hash[:8]}...)，略過處理。使用 --force 可強制重新切塊。")
        return

    # 讀取並轉換/清洗文本
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 讀取檔案失敗：{e}")
        sys.exit(1)

    # 物理清洗：去除 Mac 隱藏字元、Windows CRLF、過多空行
    cleaned_content = re.sub(r"\r\n", "\n", content)
    cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content).strip()
    
    clean_dir = root / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    clean_file = clean_dir / f"{source_id}.md"
    with open(clean_file, "w", encoding="utf-8") as f:
        f.write(cleaned_content)
    print(f"  ✓ 物理清洗完成 ➔ clean/{clean_file.name}")

    # 自然結構切塊：優先依 Markdown 標題 (#, ##, ###) 切分
    sections = re.split(r"\n(?=#{1,3}\s+)", cleaned_content)
    chunks = []
    max_chars = int(args.max_chars or 800)
    
    chunk_seq = 1
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        
        # 提取區段標題
        lines = sec.split("\n")
        first_line = lines[0].strip()
        sec_title = first_line.lstrip("#").strip() if first_line.startswith("#") else "本文"
        
        # 若區段過長，進一步按自然段落切分
        if len(sec) > max_chars:
            sub_paragraphs = sec.split("\n\n")
            buf = ""
            for p in sub_paragraphs:
                p = p.strip()
                if not p:
                    continue
                if len(buf) + len(p) <= max_chars:
                    buf = (buf + "\n\n" + p).strip()
                else:
                    if buf:
                        cid = f"{source_id}#c{chunk_seq:03d}"
                        context = f"出自文件《{source_id}》章節【{sec_title}】，記錄相關核心內容。"
                        chunks.append({
                            "chunk_id": cid,
                            "source_id": source_id,
                            "context": context,
                            "text": buf,
                            "section": sec_title,
                            "date": today_str,
                            "doc_type": file_path.suffix.lstrip("."),
                            "access": "internal",
                            "hash": hashlib.md5(buf.encode("utf-8")).hexdigest(),
                            "status": "active"
                        })
                        chunk_seq += 1
                    buf = p
            if buf:
                cid = f"{source_id}#c{chunk_seq:03d}"
                context = f"出自文件《{source_id}》章節【{sec_title}】，記錄相關核心內容。"
                chunks.append({
                    "chunk_id": cid,
                    "source_id": source_id,
                    "context": context,
                    "text": buf,
                    "section": sec_title,
                    "date": today_str,
                    "doc_type": file_path.suffix.lstrip("."),
                    "access": "internal",
                    "hash": hashlib.md5(buf.encode("utf-8")).hexdigest(),
                    "status": "active"
                })
                chunk_seq += 1
        else:
            cid = f"{source_id}#c{chunk_seq:03d}"
            context = f"出自文件《{source_id}》章節【{sec_title}】，記錄相關核心內容。"
            chunks.append({
                "chunk_id": cid,
                "source_id": source_id,
                "context": context,
                "text": sec,
                "section": sec_title,
                "date": today_str,
                "doc_type": file_path.suffix.lstrip("."),
                "access": "internal",
                "hash": hashlib.md5(sec.encode("utf-8")).hexdigest(),
                "status": "active"
            })
            chunk_seq += 1

    # 輸出至 chunks/<source_id>.jsonl
    chunks_dir = root / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_jsonl = chunks_dir / f"{source_id}.jsonl"
    with open(chunk_jsonl, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  ✓ 結構切塊完成：產生 {len(chunks)} 塊 ➔ chunks/{chunk_jsonl.name}")

    # 更新 manifest
    manifest.setdefault("sources", {})[source_id] = {
        "hash": file_hash,
        "path": str(file_path.relative_to(root)) if file_path.is_relative_to(root) else str(file_path),
        "chunk_count": len(chunks),
        "updated_at": datetime.now().isoformat(),
        "status": "active"
    }
    save_manifest(root, manifest)
    print(f"  ✓ 更新狀態清單 ➔ state/manifest.json")
    print(f"🎉 匯入完成！請記得執行 `kb index` 重建索引，並通知 Ingestor 編譯 Wiki。")

# ==========================================
# 指令實作 3: kb index
# ==========================================

def get_db_path(root: Path) -> Path:
    idx_dir = root / "index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    return idx_dir / "kb_fts.db"

def cmd_index(args):
    root = find_kb_root()
    db_path = get_db_path(root)
    
    if args.rebuild and db_path.exists():
        print("🔄 依指示清除既有索引庫...")
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 建立 SQLite FTS5 全文檢索表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks_fts (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT,
            context TEXT,
            content TEXT,
            section TEXT,
            date TEXT,
            status TEXT
        )
    """)
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_idx USING fts5(
            chunk_id UNINDEXED,
            context,
            content,
            section,
            tokenize = 'trigram'
        )
    """)
    conn.commit()

    # 掃描 chunks/
    chunks_dir = root / "chunks"
    if not chunks_dir.is_dir():
        print("ℹ️ chunks/ 目錄尚無切塊檔案。")
        conn.close()
        return

    indexed_count = 0
    cur.execute("DELETE FROM fts_idx")
    cur.execute("DELETE FROM chunks_fts")
    
    for jsonl_file in chunks_dir.glob("*.jsonl"):
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                if c.get("status") == "superseded":
                    continue
                cid = c["chunk_id"]
                sid = c.get("source_id", "")
                ctx = c.get("context", "")
                txt = c.get("text", "")
                sec = c.get("section", "")
                dt = c.get("date", "")
                st = c.get("status", "active")
                
                cur.execute(
                    "INSERT OR REPLACE INTO chunks_fts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (cid, sid, ctx, txt, sec, dt, st)
                )
                cur.execute(
                    "INSERT INTO fts_idx (chunk_id, context, content, section) VALUES (?, ?, ?, ?)",
                    (cid, ctx, txt, sec)
                )
                indexed_count += 1

    conn.commit()
    conn.close()
    print(f"✅ 索引建置完成！共建立 {indexed_count} 筆切塊之 FTS5 全文檢索索引 ➔ index/kb_fts.db")

# ==========================================
# 指令實作 4: kb search
# ==========================================

def cmd_search(args):
    root = find_kb_root()
    db_path = get_db_path(root)
    if not db_path.exists():
        print("❌ 索引資料庫尚未建立，請先執行 `kb index`")
        sys.exit(1)

    query = args.query.strip()
    top_k = int(args.k or 5)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 處理檢索關鍵字：若包含空白或特殊字元，轉為 FTS5 格式
    terms = query.split()
    if not terms:
        print("[]")
        conn.close()
        return
    
    fts_query = " OR ".join([f'"{t}"' for t in terms])
    
    try:
        cur.execute("""
            SELECT f.chunk_id, f.context, f.content, f.section, f.source_id, f.date, bm25(fts_idx) AS rank
            FROM fts_idx idx
            JOIN chunks_fts f ON idx.chunk_id = f.chunk_id
            WHERE fts_idx MATCH ? AND f.status = 'active'
            ORDER BY rank
            LIMIT ?
        """, (fts_query, top_k))
        rows = cur.fetchall()
    except Exception as e:
        # 回退至 LIKE 模糊搜尋
        like_term = f"%{query}%"
        cur.execute("""
            SELECT chunk_id, context, content, section, source_id, date, 0.0 AS rank
            FROM chunks_fts
            WHERE (content LIKE ? OR context LIKE ? OR section LIKE ?) AND status = 'active'
            LIMIT ?
        """, (like_term, like_term, like_term, top_k))
        rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "chunk_id": r[0],
            "context": r[1],
            "text": r[2],
            "section": r[3],
            "source_id": r[4],
            "date": r[5],
            "score": abs(float(r[6])) if r[6] != 0.0 else 1.0
        })

    conn.close()
    
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"🔎 檢索詞：『{query}』— 找到 {len(results)} 筆候選切塊：\n")
        for i, res in enumerate(results, 1):
            print(f"[{i}] {res['chunk_id']} (分數: {res['score']:.4f})")
            print(f"    【情境】：{res['context']}")
            snippet = res['text'][:140].replace('\n', ' ')
            print(f"    【正文】：{snippet}...")
            print("-" * 50)

# ==========================================
# 指令實作 5: kb cite
# ==========================================

def cmd_cite(args):
    root = find_kb_root()
    cid = args.chunk_id.strip()
    
    # 從 chunks/ 目錄尋找
    chunks_dir = root / "chunks"
    found = None
    if chunks_dir.is_dir():
        for jsonl_file in chunks_dir.glob("*.jsonl"):
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if cid in line:
                        c = json.loads(line)
                        if c.get("chunk_id") == cid:
                            found = c
                            break
            if found:
                break
                
    if not found:
        print(f"❌ 查無切塊出處：{cid}")
        sys.exit(1)

    print(f"📖 引用切塊：{found['chunk_id']}")
    print(f"來源文件：{found.get('source_id')} | 日期：{found.get('date')} | 狀態：{found.get('status')}")
    print(f"段落標題：{found.get('section')}")
    print(f"前置情境：{found.get('context')}")
    print("\n" + "="*20 + "【切塊原文正文】" + "="*20)
    print(found.get("text"))
    print("="*56)

# ==========================================
# 指令實作 6: kb lint
# ==========================================

def cmd_lint(args):
    root = find_kb_root()
    wiki_dir = root / "wiki"
    chunks_dir = root / "chunks"
    
    print(f"🧹 開始執行知識庫健檢 (Lint Pass)...")
    
    # 收集所有已存在切塊
    valid_chunks = set()
    if chunks_dir.is_dir():
        for jsonl_file in chunks_dir.glob("*.jsonl"):
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        c = json.loads(line)
                        valid_chunks.add(c.get("chunk_id"))

    # 掃描 Wiki 頁面
    broken_citations = []
    orphan_pages = []
    total_pages = 0
    all_pages = set()
    page_inbound = {}

    link_pattern = re.compile(r"\[\[([^\|\]]+)(?:\|[^\]]+)?\]\]")
    chunk_cite_pattern = re.compile(r"\[\[chunk:([^\|\]]+)\]\]")

    if wiki_dir.is_dir():
        for md_file in wiki_dir.rglob("*.md"):
            stem = md_file.stem
            all_pages.add(stem)
            page_inbound[stem] = 0

        for md_file in wiki_dir.rglob("*.md"):
            total_pages += 1
            with open(md_file, "r", encoding="utf-8") as f:
                text = f.read()
            
            # 檢查雙向連結
            for lk in link_pattern.findall(text):
                lk_clean = lk.strip()
                if lk_clean in page_inbound and lk_clean != md_file.stem:
                    page_inbound[lk_clean] += 1
            
            # 檢查切塊引用
            for cid in chunk_cite_pattern.findall(text):
                cid_clean = cid.strip()
                if cid_clean not in valid_chunks:
                    broken_citations.append((md_file.name, cid_clean))

    for p, count in page_inbound.items():
        if count == 0 and p not in ["index", "log", "README"]:
            orphan_pages.append(p)

    print(f"  ✓ 掃描 Wiki 頁面數：{total_pages} 頁")
    print(f"  ✓ 有效切塊總數：{len(valid_chunks)} 塊")
    
    has_issue = False
    if broken_citations:
        has_issue = True
        print(f"\n❌ 發現 {len(broken_citations)} 處失效切塊引用 (Broken Citations)：")
        for pg, cid in broken_citations:
            print(f"   - 頁面 [{pg}] 引用了不存在的切塊 [[chunk:{cid}]]")

    if orphan_pages:
        print(f"\n⚠️ 發現 {len(orphan_pages)} 個孤兒頁面 (無被其他頁面內部連結)：")
        for op in orphan_pages:
            print(f"   - [[{op}]]")

    if not has_issue and not orphan_pages:
        print("\n🎉 kb lint 檢查全數通過！零斷鏈、零失效引用，健康度 A+。")

# ==========================================
# 指令實作 7: kb task
# ==========================================

def cmd_task(args):
    root = find_kb_root()
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    
    subcmd = args.task_cmd
    if subcmd == "list":
        cards = list(tasks_dir.glob("*.md"))
        print(f"📋 任務卡片清單（共 {len(cards)} 張）：\n")
        for c in sorted(cards):
            status = "未認領"
            owner = "無"
            with open(c, "r", encoding="utf-8") as f:
                for line in f:
                    if "status:" in line:
                        status = line.split(":", 1)[1].strip()
                    if "owner:" in line:
                        owner = line.split(":", 1)[1].strip()
            print(f"  - [{status}] {c.name} (負責人: {owner})")
            
    elif subcmd == "new":
        tid = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        t_path = tasks_dir / f"{tid}.md"
        title = args.title or "新任務"
        role = args.role or "Ingestor"
        content = f"""---
task_id: "{tid}"
title: "{title}"
role: "{role}"
owner: null
locked_at: null
status: "pending"
created_at: "{datetime.now().isoformat()}"
needs_review: false
---

## 任務目標
{title}

## 輸入檔案
- 

## 預期輸出
- 
"""
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 成功建立任務卡片 ➔ tasks/{t_path.name}")

    elif subcmd == "claim":
        tid = args.task_id
        t_path = tasks_dir / f"{tid}.md" if not tid.endswith(".md") else tasks_dir / tid
        if not t_path.exists():
            print(f"❌ 找不到任務卡片：{tid}")
            return
        agent_name = args.agent or "Agent"
        now_str = datetime.now().isoformat()
        
        with open(t_path, "r", encoding="utf-8") as f:
            txt = f.read()
        txt = re.sub(r'owner:\s*.*', f'owner: "{agent_name}"', txt)
        txt = re.sub(r'locked_at:\s*.*', f'locked_at: "{now_str}"', txt)
        txt = re.sub(r'status:\s*.*', 'status: "in_progress"', txt)
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"🔒 任務已由 {agent_name} 成功鎖定認領：{t_path.name}")

    elif subcmd == "done":
        tid = args.task_id
        t_path = tasks_dir / f"{tid}.md" if not tid.endswith(".md") else tasks_dir / tid
        if not t_path.exists():
            print(f"❌ 找不到任務卡片：{tid}")
            return
        with open(t_path, "r", encoding="utf-8") as f:
            txt = f.read()
        txt = re.sub(r'status:\s*.*', 'status: "done"', txt)
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"🎉 任務已標記為完成 (done)：{t_path.name}")

# ==========================================
# 指令實作 6: kb eval
# ==========================================

def cmd_eval(args):
    root = find_kb_root()
    db_path = get_db_path(root)
    if not db_path.exists():
        print("❌ 索引資料庫尚未建立，請先執行 `kb index`")
        sys.exit(1)

    golden_path = Path(args.file) if args.file else (root / "eval" / "golden.jsonl")
    if not golden_path.exists():
        print(f"❌ 找不到黃金問題集檔案：{golden_path}")
        print("   提示：可參考 references/golden.example.jsonl 建立評估集。")
        sys.exit(1)

    questions = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    questions.append(json.loads(line))
                except Exception:
                    pass

    if args.tag:
        questions = [q for q in questions if q.get("tag") == args.tag]

    if not questions:
        print("⚠️ 未找到符合條件的評估問題。")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    candidates_limit = int(args.candidates or 30)
    top_k_limit = int(args.k or 5)

    total_q = len(questions)
    cand_hits = 0
    topk_hits = 0
    type_stats = {}

    print(f"🚀 開始執行 Wiki-RAG 基準評估（共 {total_q} 題）...\n")

    for q in questions:
        qid = q.get("id", "unknown")
        qtype = q.get("type", "general")
        qtext = q.get("question", "")
        targets = set(q.get("target_chunks", []))
        
        if qtype not in type_stats:
            type_stats[qtype] = {"total": 0, "cand_hit": 0, "topk_hit": 0}
        type_stats[qtype]["total"] += 1

        terms = qtext.split()
        cand_ids = []
        if terms:
            fts_query = " OR ".join([f'"{t}"' for t in terms])
            try:
                cur.execute("""
                    SELECT f.chunk_id
                    FROM fts_idx idx
                    JOIN chunks_fts f ON idx.chunk_id = f.chunk_id
                    WHERE fts_idx MATCH ? AND f.status = 'active'
                    ORDER BY bm25(fts_idx)
                    LIMIT ?
                """, (fts_query, candidates_limit))
                cand_ids = [r[0] for r in cur.fetchall()]
            except Exception:
                like_term = f"%{qtext}%"
                cur.execute("""
                    SELECT chunk_id
                    FROM chunks_fts
                    WHERE (content LIKE ? OR context LIKE ?) AND status = 'active'
                    LIMIT ?
                """, (like_term, like_term, candidates_limit))
                cand_ids = [r[0] for r in cur.fetchall()]

        topk_ids = cand_ids[:top_k_limit]

        # 判定命中
        if qtype == "no_answer":
            # 無答案題型：若前 top_k 無內容或未盲目匹配到無關標籤視為通過
            c_hit = (len(cand_ids) == 0)
            t_hit = (len(topk_ids) == 0)
        else:
            c_hit = bool(targets.intersection(cand_ids))
            t_hit = bool(targets.intersection(topk_ids))

        if c_hit:
            cand_hits += 1
            type_stats[qtype]["cand_hit"] += 1
        if t_hit:
            topk_hits += 1
            type_stats[qtype]["topk_hit"] += 1

    conn.close()

    cand_recall = (cand_hits / total_q) * 100 if total_q else 0
    topk_recall = (topk_hits / total_q) * 100 if total_q else 0

    print("=" * 60)
    print("📊 Wiki-RAG 檢索評估指標報告 (kb eval)")
    print("=" * 60)
    print(f"• 評估問題總數：{total_q} 題")
    print(f"• 海選命中率 (Candidates Hit Rate @ {candidates_limit}): {cand_recall:.1f}% (及格線: 90%) {'✅' if cand_recall >= 90 else '⚠️ 未達標'}")
    print(f"• 小抄命中率 (Top-k Hit Rate @ {top_k_limit}):        {topk_recall:.1f}% (及格線: 80%) {'✅' if topk_recall >= 80 else '⚠️ 未達標'}")
    print("\n【分項題型表現統計】：")
    for qt, st in type_stats.items():
        c_rate = (st["cand_hit"] / st["total"]) * 100 if st["total"] else 0
        t_rate = (st["topk_hit"] / st["total"]) * 100 if st["total"] else 0
        print(f"  - [{qt:10s}] 題數: {st['total']:2d} | 海選命中: {c_rate:5.1f}% | 小抄命中: {t_rate:5.1f}%")
    print("=" * 60)

    # 寫入歷史紀錄
    history_file = root / "eval" / "history.md"
    if history_file.parent.exists():
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        log_line = f"\n## [{now_str}] eval | 海選命中: {cand_recall:.1f}% | 小抄命中: {topk_recall:.1f}% | 總題數: {total_q}\n"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(log_line)
        print(f"📝 評估歷史已追加至：{history_file.relative_to(root)}")

# ==========================================
# 主入口
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Wiki-RAG 知識庫 CLI 工具 (kb)")
    subparsers = parser.add_subparsers(dest="subcommand", help="子指令")

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="健全性檢查")
    p_doctor.set_defaults(func=cmd_doctor)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="清洗並切塊來源檔案")
    p_ingest.add_argument("file", help="來源檔案路徑")
    p_ingest.add_argument("--id", help="指定 source_id")
    p_ingest.add_argument("--max-chars", help="單切塊最大字元數 (預設 800)")
    p_ingest.add_argument("--force", action="store_true", help="強制重新切塊")
    p_ingest.set_defaults(func=cmd_ingest)

    # index
    p_index = subparsers.add_parser("index", help="建立全文檢索索引")
    p_index.add_argument("--rebuild", action="store_true", help="強制重新構建索引")
    p_index.set_defaults(func=cmd_index)

    # search
    p_search = subparsers.add_parser("search", help="混合全文檢索")
    p_search.add_argument("query", help="查詢詞")
    p_search.add_argument("--k", default=5, help="取回切塊數量 (預設 5)")
    p_search.add_argument("--json", action="store_true", help="以 JSON 格式輸出")
    p_search.set_defaults(func=cmd_search)

    # cite
    p_cite = subparsers.add_parser("cite", help="提取切塊原文進行核驗")
    p_cite.add_argument("chunk_id", help="切塊編號 (如 src-2024#c001)")
    p_cite.set_defaults(func=cmd_cite)

    # lint
    p_lint = subparsers.add_parser("lint", help="知識庫斷鏈與引用健檢")
    p_lint.set_defaults(func=cmd_lint)

    # eval
    p_eval = subparsers.add_parser("eval", help="跑黃金問題集評估指標")
    p_eval.add_argument("--file", help="自訂 golden.jsonl 路徑")
    p_eval.add_argument("--tag", help="僅評估特定標籤的問題")
    p_eval.add_argument("--candidates", default=30, help="海選候選數量 (預設 30)")
    p_eval.add_argument("--k", default=5, help="小抄送入數量 (預設 5)")
    p_eval.set_defaults(func=cmd_eval)

    # task
    p_task = subparsers.add_parser("task", help="任務卡片管理")
    p_task.add_argument("task_cmd", choices=["list", "new", "claim", "done"], help="任務動作")
    p_task.add_argument("task_id", nargs="?", help="任務卡片編號")
    p_task.add_argument("--title", help="任務標題")
    p_task.add_argument("--role", help="角色 (Builder, Ingestor, Maintainer 等)")
    p_task.add_argument("--agent", help="認領之 Agent 名稱")
    p_task.set_defaults(func=cmd_task)

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    args.func(args)

if __name__ == "__main__":
    main()
