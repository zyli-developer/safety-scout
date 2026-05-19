"""InspectionRepo —— 对 inspections 表的 CRUD。

设计：纯函数 + 首参 connection（不抱实例、不持有 conn 生命周期）。
单测时传一个 tmp sqlite 连接即可，无需 mock。

状态机（架构 §2.5）：
    queued -> processing -> succeeded
                         \\-> failed
    （状态约束不在 repo 层强制；上层 service 负责正确流转）
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.schemas.report import ModelMeta, ReportPayload

InspectionStatus = Literal["queued", "processing", "succeeded", "failed"]


@dataclass(frozen=True)
class InspectionRow:
    id: str
    status: str  # 用 str 而非 Literal，避免 sqlite Row -> dataclass 强转
    image_path: str
    created_at: str
    updated_at: str
    report_json: str | None
    error_json: str | None
    model_meta_json: str | None


@dataclass(frozen=True)
class ErrorPayload:
    code: str
    message: str  # dev-facing
    user_message: str  # zh, 给前端


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def create(conn: sqlite3.Connection, image_path: str) -> str:
    """插入 queued 行，返回新 id。"""
    inspection_id = str(uuid.uuid4())
    now = _now_iso()
    conn.execute(
        "INSERT INTO inspections (id, status, image_path, created_at, updated_at) "
        "VALUES (?, 'queued', ?, ?, ?)",
        (inspection_id, image_path, now, now),
    )
    conn.commit()
    return inspection_id


def get(conn: sqlite3.Connection, inspection_id: str) -> InspectionRow | None:
    row = conn.execute(
        "SELECT id, status, image_path, created_at, updated_at, "
        "report_json, error_json, model_meta_json "
        "FROM inspections WHERE id = ?",
        (inspection_id,),
    ).fetchone()
    if row is None:
        return None
    return InspectionRow(**dict(row))


def update_processing(conn: sqlite3.Connection, inspection_id: str) -> None:
    conn.execute(
        "UPDATE inspections SET status='processing', updated_at=? WHERE id=?",
        (_now_iso(), inspection_id),
    )
    conn.commit()


def update_succeeded(
    conn: sqlite3.Connection,
    inspection_id: str,
    report: ReportPayload,
    meta: ModelMeta,
) -> None:
    conn.execute(
        "UPDATE inspections SET status='succeeded', updated_at=?, "
        "report_json=?, model_meta_json=? WHERE id=?",
        (
            _now_iso(),
            report.model_dump_json(),
            meta.model_dump_json(),
            inspection_id,
        ),
    )
    conn.commit()


def update_failed(
    conn: sqlite3.Connection,
    inspection_id: str,
    error: ErrorPayload,
) -> None:
    conn.execute(
        "UPDATE inspections SET status='failed', updated_at=?, error_json=? WHERE id=?",
        (
            _now_iso(),
            json.dumps(
                {
                    "code": error.code,
                    "message": error.message,
                    "user_message": error.user_message,
                },
                ensure_ascii=False,
            ),
            inspection_id,
        ),
    )
    conn.commit()


def list_orphaned_queued(conn: sqlite3.Connection) -> list[InspectionRow]:
    """启动期恢复用：查所有 status='queued' 的孤儿（进程重启前未跑完）。"""
    rows = conn.execute(
        "SELECT id, status, image_path, created_at, updated_at, "
        "report_json, error_json, model_meta_json "
        "FROM inspections WHERE status='queued'"
    ).fetchall()
    return [InspectionRow(**dict(r)) for r in rows]


def gc_older_than(conn: sqlite3.Connection, days: int = 7) -> int:
    """删除 created_at 早于 N 天前的行；返回删除条数。"""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "DELETE FROM inspections WHERE created_at < ?",
        (cutoff,),
    )
    conn.commit()
    return cursor.rowcount
