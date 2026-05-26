"""POST /api/v2/inspections/{id}/feedback 端到端集成测试。

策略：直接通过 repo 注入一条 v2 inspection 行，避免实跑 Agent SDK。
覆盖：happy path、kind 三档、404（不存在）、404（v1 inspection）、
schema 校验失败（缺 check_id / 超长 description / 无效 kind）。
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_db
from app.main import create_app
from app.rate_limit import limiter
from app.storage import inspection_repo
from app.storage.db import connect, init_schema


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """构造干净环境：tmp sqlite + TestClient + 一条 v2 inspection 预埋。

    返回 TestClient；通过 setattr 把 inspection_id 挂上去方便测试取。
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    # 预埋一条 v2 inspection（绕开实跑 Agent SDK）
    seed_conn = connect(db_path)
    init_schema(seed_conn)
    v2_id = inspection_repo.create(seed_conn, "/tmp/x.jpg", schema_version="v2")  # type: ignore[arg-type]
    v1_id = inspection_repo.create(seed_conn, "/tmp/y.jpg", schema_version="v1")  # type: ignore[arg-type]
    seed_conn.close()

    app = create_app()
    try:
        with TestClient(app) as c:
            c.v2_inspection_id = v2_id  # type: ignore[attr-defined]
            c.v1_inspection_id = v1_id  # type: ignore[attr-defined]
            yield c
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_feedback_happy_path_missed(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={
            "kind": "missed",
            "description": "工人没系安全带，模型没看到",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["inspection_id"] == env.v2_inspection_id  # type: ignore[attr-defined]
    assert body["feedback_id"]
    assert body["created_at"].endswith("Z")


def test_feedback_happy_path_false_positive(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={
            "kind": "false_positive",
            "check_id": "B01",
            "description": "其实戴了安全带",
        },
    )
    assert resp.status_code == 201, resp.text


def test_feedback_happy_path_bad_action(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={
            "kind": "bad_action",
            "check_id": "B01",
            "description": "建议的措施现场条件不允许执行",
        },
    )
    assert resp.status_code == 201, resp.text


def test_feedback_404_when_inspection_missing(env: TestClient) -> None:
    resp = env.post(
        "/api/v2/inspections/no-such-id/feedback",
        json={"kind": "missed", "description": "x"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_feedback_404_when_inspection_is_v1(env: TestClient) -> None:
    """v1 inspection 没有 check_id 概念，反馈语义对不上 —— 必须 404。"""
    resp = env.post(
        f"/api/v2/inspections/{env.v1_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "missed", "description": "x"},
    )
    assert resp.status_code == 404


def test_feedback_422_when_false_positive_missing_check_id(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "false_positive", "description": "x"},
    )
    assert resp.status_code == 422


def test_feedback_422_when_description_too_long(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "missed", "description": "x" * 501},
    )
    assert resp.status_code == 422


def test_feedback_422_when_kind_invalid(env: TestClient) -> None:
    resp = env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "other", "description": "x"},
    )
    assert resp.status_code == 422


def test_feedback_persisted_visible_via_repo(env: TestClient, tmp_path: Path) -> None:
    """反馈落地后用 repo 反查能看到 —— 端到端确认 DB write 成功。"""
    env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "missed", "description": "first"},
    )
    env.post(
        f"/api/v2/inspections/{env.v2_inspection_id}/feedback",  # type: ignore[attr-defined]
        json={"kind": "false_positive", "check_id": "B01", "description": "second"},
    )
    # 直接读 sqlite 校验落地情况
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    try:
        from app.storage import feedback_repo
        rows = feedback_repo.list_by_inspection(c, env.v2_inspection_id)  # type: ignore[attr-defined]
        assert len(rows) == 2
        assert [r.description for r in rows] == ["first", "second"]
    finally:
        c.close()
