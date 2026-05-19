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
    """打开连接 + 启 WAL + row_factory。每请求一个连接，由调用方负责 close。"""
    # 父目录不存在则建（local_data/ 等）
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    # WAL 模式：写不阻塞读，对多请求/单写的 FastAPI + BackgroundTasks 场景友好
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """幂等：建表 / 索引。首次启动 + 后续启动都跑一遍。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,            -- uuid v4 string
            status TEXT NOT NULL,           -- queued | processing | succeeded | failed
            image_path TEXT NOT NULL,       -- 绝对路径 to uploads/{uuid}.{ext}
            created_at TEXT NOT NULL,       -- ISO 8601 UTC, ...Z
            updated_at TEXT NOT NULL,       -- ISO 8601 UTC, ...Z
            report_json TEXT,               -- ReportPayload.model_dump_json()，succeeded 时非空
            error_json TEXT,                -- {code,message,user_message}，failed 时非空
            model_meta_json TEXT            -- {provider,model,latency_ms}，succeeded 时非空
        );
        CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);
        CREATE INDEX IF NOT EXISTS idx_inspections_created_at ON inspections(created_at);
    """)
    conn.commit()
