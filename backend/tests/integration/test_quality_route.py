"""GET /api/v1/quality/trend 集成测试 —— 参数校验 + 端到端响应 shape。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.schemas.report_v2 import (
    Finding,
    ReportMeta,
    ReportSummary,
    ReportV2Payload,
)
from app.storage import inspection_repo, metrics_repo
from app.storage.db import connect
from app.storage.metrics_repo import (
    InputFingerprint,
    RuntimeMetrics,
    VersionFingerprint,
)


def _set_tmp_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()


@pytest.fixture
def app_for_test(tmp_path: Path, monkeypatch) -> Iterator[Any]:
    _set_tmp_env(monkeypatch, tmp_path)
    app = create_app()
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.fixture
def client(app_for_test: Any) -> Iterator[TestClient]:
    with TestClient(app_for_test) as c:
        yield c


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def _seed_one(db_path: Path, *, prompt_version: str = "v7") -> None:
    """直连 sqlite 塞一条 metrics（用 TestClient 跑分析太重）。"""
    conn = connect(db_path)
    try:
        iid = inspection_repo.create(conn, image_path="/tmp/x.jpg", schema_version="v2")
        report = ReportV2Payload(
            report_meta=ReportMeta(
                image_summary="x",
                scene_detected=[],
                analysis_confidence="高",
                overall_risk_level="较大",
            ),
            findings=[
                Finding(
                    check_id="X01",
                    category="x",
                    status="存在隐患",
                    title="x",
                    location="x",
                    description="x",
                    severity="较大",
                    regulation="JGJ 1.1",
                    action="x",
                    confidence="高",
                )
            ],
            no_findings=[],
            uncertain=[],
            summary=ReportSummary(
                total_checks=1, findings_count=1, fatal_count=0, major_count=1,
                minor_count=0, no_issue_count=0, uncertain_count=0,
                key_recommendations=[],
            ),
        )
        metrics_repo.record_from_report(
            conn,
            iid,
            version=VersionFingerprint(
                api_version="v2", prompt_version=prompt_version,
                skill_index_version=prompt_version, model="opus-4-7",
            ),
            inp=InputFingerprint(image_sha256="x"*64, image_bytes=100),
            runtime=RuntimeMetrics(total_elapsed_ms=200000, output_tokens=5000),
            report=report,
            status="succeeded",
        )
    finally:
        conn.close()


def test_trend_returns_valid_shape(client: TestClient, tmp_path: Path) -> None:
    _seed_one(tmp_path / "test.db", prompt_version="v7")
    _seed_one(tmp_path / "test.db", prompt_version="v6")

    r = client.get("/api/v1/quality/trend?metric=p50_latency&group_by=prompt_version")
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "p50_latency"
    assert body["group_by"] == "prompt_version"
    assert "since" in body
    assert len(body["series"]) == 2
    for s in body["series"]:
        assert {"group", "x", "value", "n"} <= set(s.keys())


def test_trend_missing_metric_returns_422(client: TestClient) -> None:
    """FastAPI Query 必填参数缺失 → 422。"""
    r = client.get("/api/v1/quality/trend?group_by=prompt_version")
    assert r.status_code == 422


def test_trend_invalid_metric_returns_422(client: TestClient) -> None:
    """metric 值不在 Literal 白名单内 → FastAPI 校验失败 422。"""
    r = client.get("/api/v1/quality/trend?metric=garbage&group_by=prompt_version")
    assert r.status_code == 422


def test_trend_invalid_group_by_returns_422(client: TestClient) -> None:
    r = client.get("/api/v1/quality/trend?metric=p50_latency&group_by=garbage")
    assert r.status_code == 422


def test_trend_empty_db_returns_empty_series(client: TestClient) -> None:
    r = client.get("/api/v1/quality/trend?metric=p50_latency&group_by=prompt_version")
    assert r.status_code == 200
    assert r.json()["series"] == []


def test_trend_accepts_custom_since(client: TestClient, tmp_path: Path) -> None:
    _seed_one(tmp_path / "test.db")
    r = client.get(
        "/api/v1/quality/trend"
        "?metric=p50_latency&group_by=prompt_version&since=2020-01-01T00:00:00Z"
    )
    assert r.status_code == 200
    assert r.json()["since"] == "2020-01-01T00:00:00Z"
