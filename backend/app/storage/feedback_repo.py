"""FeedbackRepo —— 对 feedbacks 表的 CRUD。

与 inspection_repo.py 同样的设计：纯函数 + 首参 connection。

表 schema 在 db.init_schema 里建（与 inspections 表一并，幂等）。
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

FeedbackKind = Literal["false_positive", "missed", "bad_action"]


@dataclass(frozen=True)
class FeedbackRow:
    id: str
    inspection_id: str
    kind: str
    check_id: str | None
    description: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def create(
    conn: sqlite3.Connection,
    inspection_id: str,
    kind: FeedbackKind,
    check_id: str | None,
    description: str,
) -> FeedbackRow:
    """落一条反馈。返回完整 row（含生成的 id / created_at）。"""
    fid = str(uuid.uuid4())
    now = _now_iso()
    conn.execute(
        "INSERT INTO feedbacks "
        "(id, inspection_id, kind, check_id, description, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (fid, inspection_id, kind, check_id, description, now),
    )
    conn.commit()
    return FeedbackRow(
        id=fid,
        inspection_id=inspection_id,
        kind=kind,
        check_id=check_id,
        description=description,
        created_at=now,
    )


def list_by_inspection(
    conn: sqlite3.Connection, inspection_id: str
) -> list[FeedbackRow]:
    """按 inspection 反查所有反馈 —— 给运营 / 安全工程师聚合用。"""
    rows = conn.execute(
        "SELECT id, inspection_id, kind, check_id, description, created_at "
        "FROM feedbacks WHERE inspection_id = ? ORDER BY created_at ASC",
        (inspection_id,),
    ).fetchall()
    return [FeedbackRow(**dict(r)) for r in rows]
