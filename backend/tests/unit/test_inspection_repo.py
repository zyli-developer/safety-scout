"""InspectionRepo CRUD 单元测试。

每个测试拿 tmp_path 下一个全新 sqlite 文件，确保隔离 + 不污染 local_data/。
覆盖 7 个核心场景：create/get、update_processing/succeeded/failed、
list_orphaned_queued、gc_older_than。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.schemas.report import Hazard, ModelMeta, ReportPayload
from app.storage import inspection_repo as repo
from app.storage.db import connect, init_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


def _make_report(inspection_id: str = "550e8400-e29b-41d4-a716-446655440000") -> ReportPayload:
    """构造一个最小但合法的 ReportPayload，供 update_succeeded 单测复用。"""
    return ReportPayload(
        inspection_id=inspection_id,
        created_at="2026-05-19T08:00:00Z",
        plain_warning="工人未戴安全帽，立刻撤离",
        summary="现场存在 1 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="",
                suggestion="立即责令补齐安全帽",
            )
        ],
        model_meta=ModelMeta(provider="fake", model="fake-replay", latency_ms=1234),
    )


def _make_meta() -> ModelMeta:
    return ModelMeta(provider="fake", model="fake-replay", latency_ms=1234)


def test_create_and_get(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/abc.jpg")
    # uuid v4 字符串长度 36（含 4 个 dash）
    assert len(inspection_id) == 36
    assert inspection_id.count("-") == 4

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.id == inspection_id
    assert row.status == "queued"
    assert row.image_path == "/tmp/uploads/abc.jpg"
    assert row.report_json is None
    assert row.error_json is None
    assert row.model_meta_json is None
    # created_at 是 ISO 8601 UTC + Z 后缀
    assert row.created_at.endswith("Z")
    parsed = datetime.strptime(row.created_at, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.tzinfo is None  # strptime 不带 tz
    assert row.created_at == row.updated_at  # create 时两者同值


def test_get_missing_returns_none(conn: sqlite3.Connection) -> None:
    assert repo.get(conn, "00000000-0000-0000-0000-000000000000") is None


def test_update_processing_changes_status(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/x.jpg")
    before = repo.get(conn, inspection_id)
    assert before is not None

    # 确保 updated_at 能严格大于 created_at —— sqlite 时间精度是秒，sleep 1s
    # 太慢；这里直接手动倒拨 created_at 一秒来验证 update 后 updated_at > created_at。
    conn.execute(
        "UPDATE inspections SET created_at=?, updated_at=? WHERE id=?",
        ("2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z", inspection_id),
    )
    conn.commit()

    repo.update_processing(conn, inspection_id)
    after = repo.get(conn, inspection_id)
    assert after is not None
    assert after.status == "processing"
    assert after.updated_at > after.created_at  # ISO 8601 字符串可字典序比较


def test_update_succeeded_persists_report(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/y.jpg")
    report = _make_report()
    meta = _make_meta()

    repo.update_succeeded(conn, inspection_id, report, meta)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "succeeded"
    assert row.report_json is not None
    assert row.model_meta_json is not None
    assert row.error_json is None

    # round-trip: 反序列化回 ReportPayload，等价于原对象
    restored = ReportPayload.model_validate_json(row.report_json)
    assert restored == report

    restored_meta = ModelMeta.model_validate_json(row.model_meta_json)
    assert restored_meta == meta


def test_update_failed_persists_error_payload(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/z.jpg")
    err = repo.ErrorPayload(
        code="LLM_TIMEOUT",
        message="claude CLI subprocess killed after 300s",
        user_message="AI 分析超时，请稍后重试",
    )

    repo.update_failed(conn, inspection_id, err)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "failed"
    assert row.report_json is None
    assert row.model_meta_json is None
    assert row.error_json is not None

    payload = json.loads(row.error_json)
    assert payload == {
        "code": "LLM_TIMEOUT",
        "message": "claude CLI subprocess killed after 300s",
        "user_message": "AI 分析超时，请稍后重试",
    }


def test_list_orphaned_queued(conn: sqlite3.Connection) -> None:
    id_queued = repo.create(conn, image_path="/tmp/uploads/q.jpg")
    id_processing = repo.create(conn, image_path="/tmp/uploads/p.jpg")
    id_succeeded = repo.create(conn, image_path="/tmp/uploads/s.jpg")

    repo.update_processing(conn, id_processing)
    repo.update_succeeded(conn, id_succeeded, _make_report(id_succeeded), _make_meta())

    orphans = repo.list_orphaned_queued(conn)
    assert len(orphans) == 1
    assert orphans[0].id == id_queued
    assert orphans[0].status == "queued"


def test_gc_older_than(conn: sqlite3.Connection) -> None:
    old1 = repo.create(conn, image_path="/tmp/uploads/old1.jpg")
    old2 = repo.create(conn, image_path="/tmp/uploads/old2.jpg")
    today = repo.create(conn, image_path="/tmp/uploads/today.jpg")

    # 把 old1 + old2 的 created_at 倒拨到 8 天前
    eight_days_ago = "2020-01-01T00:00:00Z"  # 远早于今天，肯定 > 7 天
    conn.execute(
        "UPDATE inspections SET created_at=? WHERE id IN (?, ?)",
        (eight_days_ago, old1, old2),
    )
    conn.commit()

    deleted = repo.gc_older_than(conn, days=7)
    assert deleted == 2

    # today 仍在
    assert repo.get(conn, today) is not None
    assert repo.get(conn, old1) is None
    assert repo.get(conn, old2) is None


def test_wal_mode_active(conn: sqlite3.Connection) -> None:
    """WAL 模式可读：架构 §2.1 要求 WAL，确保 connect() 真的把它开了。"""
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_now_iso_uses_z_suffix() -> None:
    """ISO 8601 UTC 必须用 Z 后缀，不能是 +00:00（与 spec 对齐）。"""
    ts = repo._now_iso()
    assert ts.endswith("Z")
    assert "+" not in ts
    # 解析回 datetime 不应抛
    datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
