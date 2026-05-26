"""FeedbackRepo CRUD 单元测试。

每个测试拿 tmp_path 下全新 sqlite，覆盖：
- create 落 row + 自动生成 id / created_at
- list_by_inspection 按时间升序返回
- check_id NULL（missed 类反馈）正确往返
- FK 约束生效（inspection 不存在时插不进）
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.storage import feedback_repo, inspection_repo
from app.storage.db import connect, init_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


def _make_inspection(conn: sqlite3.Connection, schema_version: str = "v2") -> str:
    return inspection_repo.create(conn, "/tmp/x.jpg", schema_version=schema_version)  # type: ignore[arg-type]


def test_create_writes_row(conn: sqlite3.Connection) -> None:
    iid = _make_inspection(conn)
    row = feedback_repo.create(
        conn,
        inspection_id=iid,
        kind="false_positive",
        check_id="B01",
        description="模型误判",
    )
    assert row.id  # uuid 非空
    assert row.inspection_id == iid
    assert row.kind == "false_positive"
    assert row.check_id == "B01"
    assert row.description == "模型误判"
    assert row.created_at.endswith("Z")


def test_check_id_none_round_trips(conn: sqlite3.Connection) -> None:
    iid = _make_inspection(conn)
    feedback_repo.create(
        conn,
        inspection_id=iid,
        kind="missed",
        check_id=None,
        description="工人没系安全带",
    )
    rows = feedback_repo.list_by_inspection(conn, iid)
    assert len(rows) == 1
    assert rows[0].check_id is None


def test_list_by_inspection_ascending(conn: sqlite3.Connection) -> None:
    iid = _make_inspection(conn)
    feedback_repo.create(conn, iid, "missed", None, "first")
    feedback_repo.create(conn, iid, "false_positive", "B01", "second")
    feedback_repo.create(conn, iid, "bad_action", "B02", "third")
    rows = feedback_repo.list_by_inspection(conn, iid)
    assert [r.description for r in rows] == ["first", "second", "third"]


def test_list_empty_for_unknown_inspection(conn: sqlite3.Connection) -> None:
    assert feedback_repo.list_by_inspection(conn, "no-such-id") == []


def test_fk_enforced_on_missing_inspection(conn: sqlite3.Connection) -> None:
    """FK ON 时往不存在的 inspection 写反馈应失败。"""
    with pytest.raises(sqlite3.IntegrityError):
        feedback_repo.create(
            conn,
            inspection_id="no-such-id",
            kind="missed",
            check_id=None,
            description="x",
        )


def test_feedbacks_isolated_between_inspections(conn: sqlite3.Connection) -> None:
    a = _make_inspection(conn)
    b = _make_inspection(conn)
    feedback_repo.create(conn, a, "missed", None, "for A")
    feedback_repo.create(conn, b, "missed", None, "for B")
    assert [r.description for r in feedback_repo.list_by_inspection(conn, a)] == ["for A"]
    assert [r.description for r in feedback_repo.list_by_inspection(conn, b)] == ["for B"]
