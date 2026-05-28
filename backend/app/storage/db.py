"""SQLite 连接 / schema 初始化。

- stdlib sqlite3，不引 ORM（架构 §2.1 决定）
- WAL 模式：多 reader / 单 writer 并发友好（FastAPI 路由读 + 后台 runner 写）
- row_factory = sqlite3.Row 让 cursor 行能像 dict 访问
- schema 由 init_schema(conn) 幂等创建（CREATE TABLE IF NOT EXISTS）
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    """打开连接 + 启 WAL + row_factory。每请求一个连接，由调用方负责 close。

    `check_same_thread=False`：FastAPI 把同步依赖 `get_db` 放到 threadpool 跑（连接
    在 worker 线程创建），随后路由协程在 event-loop 线程使用同一连接 —— 默认的
    sqlite3 跨线程检查会抛 ProgrammingError。我们的约束是"每请求一个连接、连接
    不跨请求共享、连接生命周期由 yield 控制"，关掉 check_same_thread 不会引入
    真正的并发风险（WAL 又保证多连接读写不互相阻塞）。
    """
    # 父目录不存在则建（local_data/ 等）
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    # WAL 模式：写不阻塞读，对多请求/单写的 FastAPI + BackgroundTasks 场景友好
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """幂等：建表 / 索引 / 增量列。首次启动 + 后续启动都跑一遍。

    schema_version 列承载 v1/v2 报告的区分（plan §3 业务集成）：
    - 'v1' = ReportPayload（旧 hazards 结构）
    - 'v2' = ReportV2Payload（findings/no_findings/uncertain/summary 结构）
    既存数据库（pre-v2）会经过 ADD COLUMN 路径补上该列，默认 v1。
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,            -- uuid v4 string
            status TEXT NOT NULL,           -- queued | processing | succeeded | failed
            image_path TEXT NOT NULL,       -- 绝对路径 to uploads/{uuid}.{ext}
            created_at TEXT NOT NULL,       -- ISO 8601 UTC, ...Z
            updated_at TEXT NOT NULL,       -- ISO 8601 UTC, ...Z
            report_json TEXT,               -- ReportPayload.model_dump_json()，succeeded 时非空
            error_json TEXT,                -- {code,message,user_message}，failed 时非空
            model_meta_json TEXT,           -- {provider,model,latency_ms}，succeeded 时非空
            schema_version TEXT NOT NULL DEFAULT 'v1'  -- 'v1' | 'v2'
        );
        CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);
        CREATE INDEX IF NOT EXISTS idx_inspections_created_at ON inspections(created_at);

        -- v2 Badcase 反馈表（plan §5.3）：误报 / 漏报 / 建议不可执行三档。
        -- 与 inspections 1:N 关系；运营 / 安全工程师聚合后改 safety_skills/*.md。
        CREATE TABLE IF NOT EXISTS feedbacks (
            id TEXT PRIMARY KEY,            -- uuid v4
            inspection_id TEXT NOT NULL REFERENCES inspections(id),
            kind TEXT NOT NULL,             -- false_positive | missed | bad_action
            check_id TEXT,                  -- 误报 / 不可执行时必填；漏报时可空
            description TEXT NOT NULL,      -- 用户说明，≤ 500 字（在 schema 层 enforce）
            created_at TEXT NOT NULL        -- ISO 8601 UTC, ...Z
        );
        CREATE INDEX IF NOT EXISTS idx_feedbacks_inspection ON feedbacks(inspection_id);
        CREATE INDEX IF NOT EXISTS idx_feedbacks_check_id ON feedbacks(check_id);

        -- 质量追踪体系（docs/specs/quality-tracking.md）—— Layer 1 数据层。
        -- 每次分析（含失败 / 超时）写一行。与 inspections 1:1，独立 GC 策略。
        -- 失败行也必须写 —— 防幸存者偏差（只看成功样本会高估质量）。
        CREATE TABLE IF NOT EXISTS inspection_metrics (
            inspection_id            TEXT PRIMARY KEY REFERENCES inspections(id),
            -- 版本指纹（缺这个就无法说"哪个 prompt 改动让我变好了"）
            api_version              TEXT NOT NULL,     -- 'v1' | 'v2'
            prompt_version           TEXT NOT NULL,     -- v1: PROMPT_VERSION; v2: skill_index_version
            skill_index_version      TEXT,              -- safety_skills/_index.json 顶层 version
            model                    TEXT NOT NULL,     -- claude-opus-4-7 / sonnet-4-5 / ...
            -- 输入指纹
            image_sha256             TEXT NOT NULL,     -- 同图复跑去重 / 一致性分析
            image_bytes              INTEGER NOT NULL,
            run_group_id             TEXT,              -- 同图 N 次复跑绑成一组；NULL=单跑
            -- 性能 / 成本（从 model_meta_json 摘出来变列，方便 SQL）
            total_elapsed_ms         INTEGER,
            input_tokens             INTEGER,
            output_tokens            INTEGER,
            cache_read_tokens        INTEGER DEFAULT 0,
            cost_usd                 REAL,
            tool_calls               INTEGER DEFAULT 0,
            scenarios_loaded         TEXT,              -- JSON array，v1 为空数组
            cache_creation_tokens    INTEGER DEFAULT 0, -- prompt cache 写入 token；对称 cache_read_tokens
            tool_call_timings_json   TEXT,              -- JSON array，每 tool dispatch 的 ms-since-start 序列
            -- 结果形状（从 report_json 预提，避免每次 query 重新 parse 12k 字符）
            finding_count            INTEGER DEFAULT 0,
            no_finding_count         INTEGER DEFAULT 0,
            uncertain_count          INTEGER DEFAULT 0,
            severity_dist_json       TEXT,              -- {"重大":1,"较大":2,...}
            is_major_count           INTEGER DEFAULT 0,
            major_basis_filled_count INTEGER DEFAULT 0,
            reg_coverage             REAL,              -- regulation 非空的 finding 占比
            -- 状态
            status                   TEXT NOT NULL,     -- 'succeeded' | 'failed' | 'timeout'
            error_code               TEXT,
            recorded_at              TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_im_prompt_ver  ON inspection_metrics(prompt_version);
        CREATE INDEX IF NOT EXISTS idx_im_image_sha   ON inspection_metrics(image_sha256);
        CREATE INDEX IF NOT EXISTS idx_im_recorded_at ON inspection_metrics(recorded_at);
        CREATE INDEX IF NOT EXISTS idx_im_status      ON inspection_metrics(status);

        -- 质量追踪 Layer 2 评判表（docs/specs/quality-tracking.md §4.1）。
        -- 每个 (baseline, candidate) pair 跑 1 次 judge → 写 1 行（含位置去偏 2 次原始返回）。
        -- inconclusive 也写（confident=0），便于统计 judge 稳定性。
        CREATE TABLE IF NOT EXISTS quality_judgments (
            id                       TEXT PRIMARY KEY,
            image_sha256             TEXT NOT NULL,
            baseline_inspection_id   TEXT REFERENCES inspections(id),
            candidate_inspection_id  TEXT REFERENCES inspections(id),
            judge_model              TEXT NOT NULL,
            judge_rubric_version     TEXT NOT NULL,
            confident                INTEGER NOT NULL,   -- 1 = 位置去偏一致，0 = inconclusive
            -- 以下 winner_* 在 confident=0 时为 NULL；值域 'baseline'|'candidate'|'tie'
            winner_overall           TEXT,
            winner_recall            TEXT,
            winner_precision         TEXT,
            winner_regulation        TEXT,
            winner_action            TEXT,
            judge_confidence         TEXT,               -- 'high'|'medium'|'low' (judge 自评)
            overall_summary          TEXT,
            raw_json_1               TEXT NOT NULL,
            raw_json_2               TEXT NOT NULL,
            cost_usd                 REAL DEFAULT 0,
            judged_at                TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qj_image ON quality_judgments(image_sha256);
        CREATE INDEX IF NOT EXISTS idx_qj_pair  ON quality_judgments(baseline_inspection_id, candidate_inspection_id);
        CREATE INDEX IF NOT EXISTS idx_qj_judge_model ON quality_judgments(judge_model);
    """)

    # SQLite 不支持 ADD COLUMN IF NOT EXISTS，需要先探一下 PRAGMA。
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(inspections)")}
    if "schema_version" not in existing_cols:
        conn.execute(
            "ALTER TABLE inspections ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'v1'"
        )

    # inspection_metrics 增量列（旧 DB 已无 CREATE TABLE 触发 → 走 ALTER）。
    metric_cols = {row["name"] for row in conn.execute("PRAGMA table_info(inspection_metrics)")}
    if "cache_creation_tokens" not in metric_cols:
        conn.execute(
            "ALTER TABLE inspection_metrics ADD COLUMN cache_creation_tokens INTEGER DEFAULT 0"
        )
    if "tool_call_timings_json" not in metric_cols:
        conn.execute(
            "ALTER TABLE inspection_metrics ADD COLUMN tool_call_timings_json TEXT"
        )
    conn.commit()
