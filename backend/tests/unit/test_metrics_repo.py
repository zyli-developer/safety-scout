"""metrics_repo 单元测试 —— 质量追踪 Layer 1 数据层契约。

覆盖：
- 成功路径 record_from_report：v1 ReportPayload → derived 字段正确
- 成功路径 record_from_report：v2 ReportV2Payload → derived 字段正确
- 失败路径 record_failure：status=failed/timeout，无 report 也能写
- query 过滤器：since / prompt_version / status / image_sha256 / limit
- severity_dist_json / reg_coverage / is_major_count 计算正确性
- 重复 inspection_id 触发主键冲突（异常向上抛）
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.schemas.report import Hazard, ModelMeta, ReportPayload
from app.schemas.report_v2 import (
    Finding,
    NoFinding,
    ReportMeta,
    ReportSummary,
    ReportV2Payload,
    Uncertain,
)
from app.storage import inspection_repo, metrics_repo
from app.storage.db import connect, init_schema
from app.storage.metrics_repo import (
    InputFingerprint,
    RuntimeMetrics,
    VersionFingerprint,
)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


def _create_inspection(conn: sqlite3.Connection, *, schema_version: str = "v2") -> str:
    """metrics 表 FK 到 inspections.id，写 metrics 前必须先有 inspection 行。"""
    return inspection_repo.create(
        conn, image_path="/tmp/test.jpg", schema_version=schema_version  # type: ignore[arg-type]
    )


def _make_v1_report(inspection_id: str) -> ReportPayload:
    return ReportPayload(
        inspection_id=inspection_id,
        created_at="2026-05-27T00:00:00Z",
        plain_warning="工人未戴安全帽",
        summary="存在 2 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="JGJ59-2011 第 4.0.2 条",
                suggestion="立即责令补齐安全帽",
                is_major=True,
                major_basis="《...判定标准》建质规〔2024〕5号 第 11 条",
            ),
            Hazard(
                category_code="H1",
                category_name="高处坠落",
                description="临边无防护",
                severity="high",
                regulation="",  # 空 regulation —— reg_coverage 应该是 0.5
                suggestion="立即搭设防护栏",
            ),
        ],
        model_meta=ModelMeta(provider="claude_cli", model="opus-4-7", latency_ms=200),
    )


def _make_v2_report() -> ReportV2Payload:
    return ReportV2Payload(
        report_meta=ReportMeta(
            image_summary="脚手架现场",
            scene_detected=["S03"],
            analysis_confidence="高",
            overall_risk_level="重大",
        ),
        findings=[
            Finding(
                check_id="B01",
                category="高坠风险",
                status="存在隐患",
                title="临边无栏杆",
                location="图片中部",
                description="三层楼板边缘",
                severity="重大",
                regulation="JGJ80-2016 第 4.1.1 条",
                action="立即搭设防护栏",
                confidence="高",
                is_major=True,
                major_basis="《...判定标准》建质规〔2024〕5号 第 6 条",
            ),
            Finding(
                check_id="C03",
                category="施工用电",
                status="存在隐患",
                title="电线裸露",
                location="墙体开口处",
                description="多根电线无固定",
                severity="较大",
                regulation="JGJ46-2005 第 7.2 条",
                action="规范敷设",
                confidence="中",
            ),
            Finding(
                check_id="A03",
                category="人员防护",
                status="存在隐患",
                title="未穿反光背心",
                location="右中部",
                description="工人穿深色衣物",
                severity="一般",
                regulation="",  # 空 → reg_coverage 应是 2/3
                action="补发反光背心",
                confidence="高",
            ),
        ],
        no_findings=[NoFinding(check_id="A01", note="均佩戴安全帽")],
        uncertain=[
            Uncertain(
                check_id="A05",
                reason="无法判断",
                suggested_action="现场核查",
            )
        ],
        summary=ReportSummary(
            total_checks=50,
            findings_count=3,
            fatal_count=1,
            major_count=1,
            minor_count=1,
            no_issue_count=45,
            uncertain_count=1,
            key_recommendations=["立即搭设防护栏"],
        ),
    )


# === record_from_report (v1) ===


def test_record_v1_report_derives_correct_summary(conn: sqlite3.Connection) -> None:
    iid = _create_inspection(conn, schema_version="v1")
    report = _make_v1_report(iid)

    metrics_repo.record_from_report(
        conn,
        iid,
        version=VersionFingerprint(api_version="v1", prompt_version="v7", model="opus-4-7"),
        inp=InputFingerprint(image_sha256="a" * 64, image_bytes=12345),
        runtime=RuntimeMetrics(total_elapsed_ms=92000, cost_usd=0.05),
        report=report,
        status="succeeded",
    )

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["api_version"] == "v1"
    assert row["prompt_version"] == "v7"
    assert row["model"] == "opus-4-7"
    assert row["image_sha256"] == "a" * 64
    assert row["finding_count"] == 2
    assert row["no_finding_count"] == 0  # v1 没有这个概念
    assert row["uncertain_count"] == 0
    # reg_coverage: 2 个 hazard，1 个 regulation 非空 = 0.5
    assert row["reg_coverage"] == 0.5
    assert row["is_major_count"] == 1
    assert row["major_basis_filled_count"] == 1
    dist = json.loads(row["severity_dist_json"])
    assert dist == {"high": 2, "medium": 0, "low": 0}
    assert row["status"] == "succeeded"


# === record_from_report (v2) ===


def test_record_v2_report_derives_correct_summary(conn: sqlite3.Connection) -> None:
    iid = _create_inspection(conn, schema_version="v2")
    report = _make_v2_report()

    metrics_repo.record_from_report(
        conn,
        iid,
        version=VersionFingerprint(
            api_version="v2",
            prompt_version="1.0.0",
            skill_index_version="1.0.0",
            model="claude-opus-4-7",
        ),
        inp=InputFingerprint(image_sha256="b" * 64, image_bytes=999),
        runtime=RuntimeMetrics(
            total_elapsed_ms=231000,
            input_tokens=19,
            output_tokens=12000,
            cost_usd=0.5569,
            tool_calls=7,
            scenarios_loaded=["S03", "S05", "S07"],
        ),
        report=report,
        status="succeeded",
    )

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["finding_count"] == 3
    assert row["no_finding_count"] == 1
    assert row["uncertain_count"] == 1
    # reg_coverage: 3 finding，2 个 regulation 非空 = 2/3
    assert abs(row["reg_coverage"] - 2 / 3) < 1e-6
    assert row["is_major_count"] == 1
    assert row["major_basis_filled_count"] == 1
    dist = json.loads(row["severity_dist_json"])
    assert dist == {"重大": 1, "较大": 1, "一般": 1, "低": 0}
    # 运行期统计原样保留
    assert row["input_tokens"] == 19
    assert row["output_tokens"] == 12000
    assert row["tool_calls"] == 7
    assert json.loads(row["scenarios_loaded"]) == ["S03", "S05", "S07"]
    # 未传 cache / timings → 默认 0 / NULL
    assert row["cache_read_tokens"] == 0
    assert row["cache_creation_tokens"] == 0
    assert row["tool_call_timings_json"] is None


def test_record_persists_cache_tokens_and_tool_timings(conn: sqlite3.Connection) -> None:
    """新增字段：cache_creation_tokens 单独写、tool_call_timings_json 原样 round-trip。

    覆盖：
    - cache_read / cache_creation 两列独立写、独立读
    - tool_call_timings 序列化为 JSON 列、反序列化结构完整（含可选 scenario_id 字段）
    """
    iid = _create_inspection(conn, schema_version="v2")
    timings = [
        {"seq": 1, "name": "load_scenario_skill", "scenario_id": "S05", "dispatched_ms": 1500},
        {"seq": 2, "name": "load_scenario_skill", "scenario_id": "S03", "dispatched_ms": 1500},
        {"seq": 3, "name": "Read", "dispatched_ms": 18200},
        {"seq": 4, "name": "submit_safety_report", "dispatched_ms": 290000},
    ]
    metrics_repo.record_from_report(
        conn,
        iid,
        version=VersionFingerprint(api_version="v2", prompt_version="1.0.0", model="opus-4-7"),
        inp=InputFingerprint(image_sha256="d" * 64, image_bytes=1024),
        runtime=RuntimeMetrics(
            total_elapsed_ms=357000,
            input_tokens=21,
            output_tokens=22000,
            cache_read_tokens=9000,
            cache_creation_tokens=2500,
            cost_usd=1.28,
            tool_calls=4,
            scenarios_loaded=["S05", "S03"],
            tool_call_timings=timings,
        ),
        report=_make_v2_report(),
        status="succeeded",
    )

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["cache_read_tokens"] == 9000
    assert row["cache_creation_tokens"] == 2500
    parsed = json.loads(row["tool_call_timings_json"])
    assert parsed == timings  # 包括可选 scenario_id 字段全保真
    assert len(parsed) == 4
    assert parsed[0]["scenario_id"] == "S05"
    assert "scenario_id" not in parsed[2]  # Read 没 scenario_id 字段不应被注入


def test_record_failure_can_carry_partial_cache_tokens(conn: sqlite3.Connection) -> None:
    """超时路径也可能已经发生 cache write（如模型卡在最后一轮）—— 失败行也要能写。"""
    iid = _create_inspection(conn)
    metrics_repo.record_failure(
        conn,
        iid,
        version=VersionFingerprint(api_version="v2", prompt_version="1.0.0", model="opus-4-7"),
        inp=InputFingerprint(image_sha256="e" * 64, image_bytes=1),
        runtime=RuntimeMetrics(
            total_elapsed_ms=300000,
            cache_read_tokens=5000,
            cache_creation_tokens=1000,
            tool_call_timings=[{"seq": 1, "name": "Read", "dispatched_ms": 800}],
        ),
        status="timeout",
        error_code="LLM_TIMEOUT",
    )

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "timeout"
    assert row["cache_read_tokens"] == 5000
    assert row["cache_creation_tokens"] == 1000
    parsed = json.loads(row["tool_call_timings_json"])
    assert parsed == [{"seq": 1, "name": "Read", "dispatched_ms": 800}]


# === record_failure ===


def test_record_failure_writes_row_without_report(conn: sqlite3.Connection) -> None:
    """失败 / 超时也必须有指标行 —— 防幸存者偏差。"""
    iid = _create_inspection(conn)

    metrics_repo.record_failure(
        conn,
        iid,
        version=VersionFingerprint(api_version="v2", prompt_version="1.0.0", model="opus-4-7"),
        inp=InputFingerprint(image_sha256="c" * 64, image_bytes=500),
        runtime=RuntimeMetrics(total_elapsed_ms=360000),
        status="timeout",
        error_code="LLM_TIMEOUT",
    )

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "timeout"
    assert row["error_code"] == "LLM_TIMEOUT"
    assert row["finding_count"] == 0
    assert row["severity_dist_json"] is None
    assert row["total_elapsed_ms"] == 360000


def test_record_failure_rejects_succeeded_status(conn: sqlite3.Connection) -> None:
    """record_failure 不应被滥用为成功路径入口。"""
    iid = _create_inspection(conn)
    with pytest.raises(AssertionError):
        metrics_repo.record_failure(
            conn,
            iid,
            version=VersionFingerprint(api_version="v2", prompt_version="x", model="x"),
            inp=InputFingerprint(image_sha256="x" * 64, image_bytes=1),
            runtime=RuntimeMetrics(total_elapsed_ms=1),
            status="succeeded",  # type: ignore[arg-type]
            error_code=None,
        )


def test_duplicate_inspection_id_raises(conn: sqlite3.Connection) -> None:
    """同 inspection 写两次指标 → 主键冲突。调用方自己防御。"""
    iid = _create_inspection(conn)
    report = _make_v2_report()
    common = dict(
        version=VersionFingerprint(api_version="v2", prompt_version="x", model="x"),
        inp=InputFingerprint(image_sha256="x" * 64, image_bytes=1),
        runtime=RuntimeMetrics(total_elapsed_ms=1),
        report=report,
    )
    metrics_repo.record_from_report(conn, iid, **common, status="succeeded")
    with pytest.raises(sqlite3.IntegrityError):
        metrics_repo.record_from_report(conn, iid, **common, status="succeeded")


# === query 过滤 ===


def _bulk_insert(
    conn: sqlite3.Connection,
    *,
    api_version: str,
    prompt_version: str,
    image_sha: str,
    status: str,
) -> str:
    iid = _create_inspection(
        conn, schema_version="v2" if api_version == "v2" else "v1"
    )
    metrics_repo.record_from_report(
        conn,
        iid,
        version=VersionFingerprint(
            api_version=api_version,  # type: ignore[arg-type]
            prompt_version=prompt_version,
            model="opus-4-7",
        ),
        inp=InputFingerprint(image_sha256=image_sha, image_bytes=1),
        runtime=RuntimeMetrics(total_elapsed_ms=1),
        report=_make_v2_report(),
        status=status,  # type: ignore[arg-type]
    )
    return iid


def test_query_filters_by_prompt_version(conn: sqlite3.Connection) -> None:
    _bulk_insert(conn, api_version="v2", prompt_version="1.0.0", image_sha="a"*64, status="succeeded")
    _bulk_insert(conn, api_version="v2", prompt_version="1.1.0", image_sha="b"*64, status="succeeded")
    _bulk_insert(conn, api_version="v2", prompt_version="1.0.0", image_sha="c"*64, status="succeeded")

    rows = metrics_repo.query(conn, prompt_version="1.0.0")
    assert len(rows) == 2
    assert all(r["prompt_version"] == "1.0.0" for r in rows)


def test_query_filters_by_status(conn: sqlite3.Connection) -> None:
    _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha="a"*64, status="succeeded")
    _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha="b"*64, status="succeeded")
    # 单独造一个失败行（不走 _bulk_insert，避免 record_from_report）
    iid = _create_inspection(conn)
    metrics_repo.record_failure(
        conn,
        iid,
        version=VersionFingerprint(api_version="v2", prompt_version="x", model="x"),
        inp=InputFingerprint(image_sha256="f"*64, image_bytes=1),
        runtime=RuntimeMetrics(total_elapsed_ms=1),
        status="failed",
        error_code="INTERNAL",
    )

    succ = metrics_repo.query(conn, status="succeeded")
    fail = metrics_repo.query(conn, status="failed")
    assert len(succ) == 2
    assert len(fail) == 1
    assert fail[0]["error_code"] == "INTERNAL"


def test_query_filters_by_image_sha_for_repeat_analysis(conn: sqlite3.Connection) -> None:
    """同图复跑分析用 image_sha256 group by 算方差 —— 必须能精确过滤。"""
    same_sha = "z" * 64
    _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha=same_sha, status="succeeded")
    _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha=same_sha, status="succeeded")
    _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha="other"*12+"x"*4, status="succeeded")

    rows = metrics_repo.query(conn, image_sha256=same_sha)
    assert len(rows) == 2


def test_query_respects_limit(conn: sqlite3.Connection) -> None:
    for i in range(5):
        _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha=str(i)*64, status="succeeded")
        time.sleep(0.001)  # 确保 recorded_at 排序稳定（同秒内插入序保留）

    rows = metrics_repo.query(conn, limit=3)
    assert len(rows) == 3


def test_query_orders_by_recorded_at_desc(conn: sqlite3.Connection) -> None:
    """最新的在前 —— 给 CSV / dashboard 用。"""
    iid_old = _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha="1"*64, status="succeeded")
    time.sleep(0.01)
    iid_new = _bulk_insert(conn, api_version="v2", prompt_version="x", image_sha="2"*64, status="succeeded")

    rows = metrics_repo.query(conn)
    assert rows[0]["inspection_id"] == iid_new
    assert rows[1]["inspection_id"] == iid_old
