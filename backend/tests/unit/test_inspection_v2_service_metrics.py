"""v2 inspection_service 写 metrics 行为单测 —— 质量追踪 Layer 1 v2 路径契约。

策略：monkeypatch app.services.inspection_v2.analyze_image，避免真打 Claude。
覆盖：v2 成功 / 失败 / 超时 三条路径都写一行 inspection_metrics。
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings
from app.errors import LLMCallError, LLMTimeoutError
from app.safety_agent.agent import AgentRunStats
from app.safety_agent.loader import SkillLoader
from app.schemas.report_v2 import (
    Finding,
    ReportMeta,
    ReportSummary,
    ReportV2Payload,
)
from app.services import inspection_v2 as service
from app.storage import inspection_repo, metrics_repo
from app.storage.db import connect, init_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "safety_skills"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def skill_loader() -> SkillLoader:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"safety_skills 未部署到 {SKILLS_ROOT}")
    return SkillLoader(SKILLS_ROOT)


@pytest.fixture
def settings() -> Settings:
    return Settings(agent_timeout_seconds=5, safety_skills_root=SKILLS_ROOT)


def _make_v2_report() -> ReportV2Payload:
    return ReportV2Payload(
        report_meta=ReportMeta(
            image_summary="脚手架现场",
            scene_detected=["S03"],
            analysis_confidence="高",
            overall_risk_level="较大",
        ),
        findings=[
            Finding(
                check_id="B01",
                category="高坠",
                status="存在隐患",
                title="临边无栏杆",
                location="图片中部",
                description="三层楼板边缘",
                severity="较大",
                regulation="JGJ80-2016 第 4.1.1 条",
                action="搭设栏杆",
                confidence="高",
            )
        ],
        no_findings=[],
        uncertain=[],
        summary=ReportSummary(
            total_checks=10,
            findings_count=1,
            fatal_count=0,
            major_count=1,
            minor_count=0,
            no_issue_count=9,
            uncertain_count=0,
            key_recommendations=["立即停工搭设栏杆"],
        ),
    )


def _make_stats() -> AgentRunStats:
    s = AgentRunStats()
    s.elapsed_ms = 231000
    s.tool_calls = 7
    s.scenarios_loaded = ["S03", "S05"]
    s.input_tokens = 19
    s.output_tokens = 12000
    s.cache_read_tokens = 8500
    s.cache_creation_tokens = 1200
    s.cost_usd = 0.5569
    s.tool_call_timings = [
        {"seq": 1, "name": "load_scenario_skill", "scenario_id": "S03", "dispatched_ms": 1500},
        {"seq": 2, "name": "load_scenario_skill", "scenario_id": "S05", "dispatched_ms": 1500},
        {"seq": 3, "name": "Read", "dispatched_ms": 9000},
        {"seq": 4, "name": "submit_safety_report", "dispatched_ms": 220000},
    ]
    return s


# === 成功 ===


async def test_v2_success_writes_metrics_row(
    monkeypatch, conn, settings, skill_loader
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/a.jpg", schema_version="v2")

    async def fake_analyze(image_bytes, settings, skill_loader, extra_context=""):
        return _make_v2_report(), _make_stats()

    monkeypatch.setattr(service, "analyze_image", fake_analyze)

    await service.run_inspection_v2(iid, b"img-bytes", conn, settings, skill_loader)

    row = metrics_repo.get(conn, iid)
    assert row is not None, "v2 成功路径必须写一行 inspection_metrics"
    assert row["status"] == "succeeded"
    assert row["api_version"] == "v2"
    assert row["prompt_version"] == skill_loader.index_version
    assert row["skill_index_version"] == skill_loader.index_version
    assert row["model"] == settings.agent_model
    assert row["finding_count"] == 1
    # 运行期指标原样保留
    assert row["input_tokens"] == 19
    assert row["output_tokens"] == 12000
    assert row["cost_usd"] == pytest.approx(0.5569)
    assert row["tool_calls"] == 7
    # cache token + tool timing 必须从 stats 透传到 metrics 行
    assert row["cache_read_tokens"] == 8500
    assert row["cache_creation_tokens"] == 1200
    import json as _json
    timings = _json.loads(row["tool_call_timings_json"])
    assert len(timings) == 4
    assert timings[0]["scenario_id"] == "S03"
    assert timings[-1]["name"] == "submit_safety_report"
    # image_sha256 准确
    expected_sha = hashlib.sha256(b"img-bytes").hexdigest()
    assert row["image_sha256"] == expected_sha
    # model_meta_json 也要带这些字段（供前端 / 调试直接展示）
    import json as _json2
    meta = _json2.loads(
        conn.execute("SELECT model_meta_json FROM inspections WHERE id=?", (iid,)).fetchone()[0]
    )
    assert meta["cache_read_tokens"] == 8500
    assert meta["cache_creation_tokens"] == 1200
    assert meta["tool_call_timings"][0]["scenario_id"] == "S03"


# === 失败：LLMCallError ===


async def test_v2_failure_writes_metrics_row(
    monkeypatch, conn, settings, skill_loader
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/b.jpg", schema_version="v2")

    async def fake_analyze(image_bytes, settings, skill_loader, extra_context=""):
        raise LLMCallError("simulated SDK failure")

    monkeypatch.setattr(service, "analyze_image", fake_analyze)

    await service.run_inspection_v2(iid, b"img", conn, settings, skill_loader)

    row = metrics_repo.get(conn, iid)
    assert row is not None, "v2 失败路径也必须写指标"
    assert row["status"] == "failed"
    assert row["error_code"] == "LLM_CALL_FAILED"
    assert row["finding_count"] == 0
    assert row["severity_dist_json"] is None
    # 即便失败，版本指纹必填
    assert row["api_version"] == "v2"
    assert row["model"] == settings.agent_model


# === 超时 ===


async def test_v2_timeout_writes_metrics_row_with_timeout_status(
    monkeypatch, conn, settings, skill_loader
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/c.jpg", schema_version="v2")

    async def fake_analyze(image_bytes, settings, skill_loader, extra_context=""):
        raise LLMTimeoutError("simulated timeout")

    monkeypatch.setattr(service, "analyze_image", fake_analyze)

    await service.run_inspection_v2(iid, b"img", conn, settings, skill_loader)

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "timeout", "LLMTimeoutError → timeout 不是 failed"
    assert row["error_code"] == "LLM_TIMEOUT"


# === 未预期异常 ===


async def test_v2_unexpected_exception_writes_metrics_row(
    monkeypatch, conn, settings, skill_loader
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/d.jpg", schema_version="v2")

    async def fake_analyze(image_bytes, settings, skill_loader, extra_context=""):
        raise ValueError("unexpected")

    monkeypatch.setattr(service, "analyze_image", fake_analyze)

    await service.run_inspection_v2(iid, b"img", conn, settings, skill_loader)

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error_code"] == "INTERNAL"
