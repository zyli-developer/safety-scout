"""v2 路由端到端集成测试：POST /api/v2/analyze → 后台 runner → GET 轮询。

策略：monkeypatch `app.services.inspection_v2.analyze_image` 为 fake，避免实跑
Claude Agent SDK。这样测的是 routes/service/runner/storage 的串联语义，
不是 LLM 行为本身（LLM 行为属于 Phase 4 集成测试 + 真实图）。
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import LLMCallError
from app.main import create_app
from app.rate_limit import limiter
from app.safety_agent.agent import AgentRunStats
from app.schemas.report_v2 import ReportV2Payload
from app.services import inspection_v2 as svc_v2

_FIXTURES_DIR_IMG = Path(__file__).resolve().parents[1] / "fixtures" / "images"
_CASE_001_IMG_PATH = _FIXTURES_DIR_IMG / "case_001_stepladder_over_2_meters.jpg"


VALID_REPORT_DICT: dict[str, Any] = {
    "report_meta": {
        "image_summary": "人字梯作业，工人在 2m 以上无防护",
        "scene_detected": ["S06"],
        "analysis_confidence": "高",
        "overall_risk_level": "较大",
    },
    "findings": [
        {
            "check_id": "B01",
            "category": "高坠风险",
            "status": "存在隐患",
            "title": "人字梯超过 2m 无防护",
            "location": "图片中部",
            "description": "工人立于人字梯顶端约 2.2m 高度，未系安全带",
            "severity": "较大",
            "regulation": "JGJ80-2016",
            "action": "立即下梯，改用脚手架或佩戴安全带",
            "confidence": "高",
        }
    ],
    "no_findings": [],
    "uncertain": [],
    "summary": {
        "total_checks": 35,
        "findings_count": 1,
        "fatal_count": 0,
        "major_count": 1,
        "minor_count": 0,
        "no_issue_count": 30,
        "uncertain_count": 4,
        "key_recommendations": ["禁止 2m 以上无防护作业"],
    },
}


def _fake_report() -> ReportV2Payload:
    return ReportV2Payload.model_validate(VALID_REPORT_DICT)


def _fake_stats() -> AgentRunStats:
    s = AgentRunStats()
    s.tool_calls = 3
    s.scenarios_loaded = ["S06"]
    s.elapsed_ms = 2500
    s.input_tokens = 5000
    s.output_tokens = 1200
    s.cost_usd = 0.018
    return s


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


def _build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    # safety_skills_root 默认指向 repo 根；测试不实跑 LLM，因此 loader 还需要
    # 真实文件（PromptBuilder 不会被调到，但 build_safety_tools 在 fake 路径上也不跑）。
    get_settings.cache_clear()

    app = create_app()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def _poll(
    client: TestClient, inspection_id: str, timeout_s: float = 5.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v2/inspections/{inspection_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] not in {"queued", "processing"}:
            return last
        time.sleep(0.1)
    pytest.fail(f"v2 轮询 {timeout_s}s 后状态仍 {last.get('status')!r}; last={last}")


def test_v2_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST → fake analyze_image 注入伪报告 → GET 看到 succeeded + v2 schema。"""

    async def fake_analyze(image_bytes, settings, skill_loader, extra_context=""):
        return _fake_report(), _fake_stats()

    monkeypatch.setattr(svc_v2, "analyze_image", fake_analyze)

    client_iter = _build_client(tmp_path, monkeypatch)
    client = next(client_iter)
    try:
        image_bytes = _CASE_001_IMG_PATH.read_bytes()
        post = client.post(
            "/api/v2/analyze",
            files={"image": ("case_001.jpg", image_bytes, "image/jpeg")},
        )
        assert post.status_code == 202, post.text
        body = post.json()
        assert body["status"] == "queued"
        assert body["poll_url"] == f"/api/v2/inspections/{body['inspection_id']}"
        inspection_id = body["inspection_id"]

        result = _poll(client, inspection_id)
        assert result["status"] == "succeeded", result
        assert result["error"] is None
        report = result["report"]
        assert report is not None
        assert report["report_meta"]["scene_detected"] == ["S06"]
        assert report["findings"][0]["check_id"] == "B01"
        assert report["findings"][0]["severity"] == "较大"
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)


def test_v2_failure_propagates_to_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """analyze_image 抛 LLMCallError → 标 failed → GET 拿到 error envelope。"""

    async def boom(*args, **kwargs):
        raise LLMCallError("Agent 没调 submit_safety_report")

    monkeypatch.setattr(svc_v2, "analyze_image", boom)

    client_iter = _build_client(tmp_path, monkeypatch)
    client = next(client_iter)
    try:
        image_bytes = _CASE_001_IMG_PATH.read_bytes()
        post = client.post(
            "/api/v2/analyze",
            files={"image": ("x.jpg", image_bytes, "image/jpeg")},
        )
        assert post.status_code == 202
        inspection_id = post.json()["inspection_id"]

        result = _poll(client, inspection_id, timeout_s=5.0)
        assert result["status"] == "failed", result
        assert result["report"] is None
        err = result["error"]
        assert err is not None
        assert err["code"] == "LLM_CALL_FAILED"
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)


def test_v2_get_404_for_unknown_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_iter = _build_client(tmp_path, monkeypatch)
    client = next(client_iter)
    try:
        resp = client.get("/api/v2/inspections/does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)


def test_v2_get_404_for_v1_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v1 创建的 inspection 不应能从 v2 GET 取到 —— 路径隔离。"""
    client_iter = _build_client(tmp_path, monkeypatch)
    client = next(client_iter)
    try:
        # 直接用 repo 插一条 v1 行
        from app.config import get_settings as _gs
        from app.storage import inspection_repo as repo
        from app.storage.db import connect

        conn = connect(_gs().sqlite_path)
        v1_id = repo.create(conn, "/tmp/fake.jpg", schema_version="v1")
        conn.close()

        resp = client.get(f"/api/v2/inspections/{v1_id}")
        assert resp.status_code == 404
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)
