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
    """)

    # SQLite 不支持 ADD COLUMN IF NOT EXISTS，需要先探一下 PRAGMA。
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(inspections)")}
    if "schema_version" not in existing_cols:
        conn.execute(
            "ALTER TABLE inspections ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'v1'"
        )
    conn.commit()
