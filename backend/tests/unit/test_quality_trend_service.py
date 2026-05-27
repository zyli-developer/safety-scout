"""quality_trend service 单测 —— 5 metric × 3 group_by 矩阵覆盖。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.quality.judge_service import PairVerdict
from app.schemas.report_v2 import (
    Finding,
    ReportMeta,
    ReportSummary,
    ReportV2Payload,
)
from app.services.quality_trend import (
    VALID_GROUP_BYS,
    VALID_METRICS,
    trend,
)
from app.storage import inspection_repo, judgments_repo, metrics_repo
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


def _seed_inspection(
    conn: sqlite3.Connection,
    *,
    prompt_version: str,
    model: str = "opus-4-7",
    elapsed_ms: int = 200000,
    output_tokens: int = 8000,
    finding_count: int = 3,
    reg_coverage: float = 0.8,
    image_sha: str = "x" * 64,
    status: str = "succeeded",
) -> str:
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
                check_id=f"X{i:02d}",
                category="x",
                status="存在隐患",
                title="x",
                location="x",
                description="x",
                severity="较大",
                regulation="JGJ 1.1" if i < int(finding_count * reg_coverage) else "",
                action="x",
                confidence="高",
            )
            for i in range(finding_count)
        ],
        no_findings=[],
        uncertain=[],
        summary=ReportSummary(
            total_checks=10, findings_count=finding_count,
            fatal_count=0, major_count=finding_count, minor_count=0,
            no_issue_count=10 - finding_count, uncertain_count=0,
            key_recommendations=[],
        ),
    )
    metrics_repo.record_from_report(
        conn,
        iid,
        version=VersionFingerprint(
            api_version="v2", prompt_version=prompt_version,
            skill_index_version=prompt_version, model=model,
        ),
        inp=InputFingerprint(image_sha256=image_sha, image_bytes=100),
        runtime=RuntimeMetrics(
            total_elapsed_ms=elapsed_ms,
            output_tokens=output_tokens,
        ),
        report=report,
        status=status,  # type: ignore[arg-type]
    )
    return iid


def _seed_judgment(
    conn: sqlite3.Connection,
    *,
    baseline_iid: str,
    candidate_iid: str,
    image_sha: str = "x" * 64,
    winner: str = "candidate",  # 'candidate' | 'baseline' | 'tie'
    confident: bool = True,
) -> None:
    verdict = PairVerdict(
        id=f"vid-{baseline_iid[:6]}-{candidate_iid[:6]}",
        baseline_inspection_id=baseline_iid,
        candidate_inspection_id=candidate_iid,
        judge_model="sonnet-test",
        judge_rubric_version="1.0",
        confident=confident,
        winner_overall=winner if confident else None,  # type: ignore[arg-type]
        winner_recall=winner if confident else None,  # type: ignore[arg-type]
        winner_precision=winner if confident else None,  # type: ignore[arg-type]
        winner_regulation=winner if confident else None,  # type: ignore[arg-type]
        winner_action=winner if confident else None,  # type: ignore[arg-type]
        confidence_self="high",
        overall_summary="x",
        raw_json_1="{}",
        raw_json_2="{}",
    )
    judgments_repo.record(conn, verdict, image_sha256=image_sha)


# === 各 metric × group_by ===


def test_p50_latency_by_prompt_version(conn: sqlite3.Connection) -> None:
    _seed_inspection(conn, prompt_version="v6", elapsed_ms=200000, image_sha="a"*64)
    _seed_inspection(conn, prompt_version="v6", elapsed_ms=240000, image_sha="b"*64)
    _seed_inspection(conn, prompt_version="v7", elapsed_ms=150000, image_sha="c"*64)

    result = trend(conn, metric="p50_latency", group_by="prompt_version")
    assert result["metric"] == "p50_latency"
    assert len(result["series"]) == 2
    by_group = {s["group"]: s for s in result["series"]}
    assert by_group["v6"]["value"] == 220000.0  # median(200000, 240000)
    assert by_group["v7"]["value"] == 150000.0
    assert by_group["v6"]["n"] == 2
    assert by_group["v7"]["n"] == 1


def test_output_tokens_by_model(conn: sqlite3.Connection) -> None:
    _seed_inspection(conn, prompt_version="x", model="opus", output_tokens=10000, image_sha="a"*64)
    _seed_inspection(conn, prompt_version="x", model="sonnet", output_tokens=5000, image_sha="b"*64)

    result = trend(conn, metric="output_tokens", group_by="model")
    by_group = {s["group"]: s for s in result["series"]}
    assert by_group["opus"]["value"] == 10000.0
    assert by_group["sonnet"]["value"] == 5000.0


def test_finding_count_by_day(conn: sqlite3.Connection) -> None:
    _seed_inspection(conn, prompt_version="x", finding_count=3, image_sha="a"*64)
    _seed_inspection(conn, prompt_version="x", finding_count=5, image_sha="b"*64)

    result = trend(conn, metric="finding_count", group_by="day")
    # 都是今天 → 一个 group
    assert len(result["series"]) == 1
    assert result["series"][0]["value"] == 4.0  # median(3, 5)
    assert result["series"][0]["n"] == 2


def test_reg_coverage_by_prompt_version(conn: sqlite3.Connection) -> None:
    _seed_inspection(conn, prompt_version="v6", reg_coverage=0.5, finding_count=4, image_sha="a"*64)
    _seed_inspection(conn, prompt_version="v7", reg_coverage=1.0, finding_count=4, image_sha="b"*64)

    result = trend(conn, metric="reg_coverage", group_by="prompt_version")
    by_group = {s["group"]: s for s in result["series"]}
    # _seed_inspection 算实际的 reg_coverage = floor(4*0.5)/4 = 2/4 = 0.5
    assert by_group["v6"]["value"] == 0.5
    assert by_group["v7"]["value"] == 1.0


# === judge_win_rate ===


def test_judge_win_rate_by_prompt_version(conn: sqlite3.Connection) -> None:
    """3 个 v7 candidate 中 2 个赢 → 67%。"""
    b1 = _seed_inspection(conn, prompt_version="v6", image_sha="a"*64)
    c1 = _seed_inspection(conn, prompt_version="v7", image_sha="a"*64)
    b2 = _seed_inspection(conn, prompt_version="v6", image_sha="b"*64)
    c2 = _seed_inspection(conn, prompt_version="v7", image_sha="b"*64)
    b3 = _seed_inspection(conn, prompt_version="v6", image_sha="c"*64)
    c3 = _seed_inspection(conn, prompt_version="v7", image_sha="c"*64)

    _seed_judgment(conn, baseline_iid=b1, candidate_iid=c1, image_sha="a"*64, winner="candidate")
    _seed_judgment(conn, baseline_iid=b2, candidate_iid=c2, image_sha="b"*64, winner="candidate")
    _seed_judgment(conn, baseline_iid=b3, candidate_iid=c3, image_sha="c"*64, winner="baseline")

    result = trend(conn, metric="judge_win_rate", group_by="prompt_version")
    by_group = {s["group"]: s for s in result["series"]}
    # candidate 是 v7，3 次中 2 次赢 = 0.6667
    assert "v7" in by_group
    assert abs(by_group["v7"]["value"] - 2 / 3) < 1e-3
    assert by_group["v7"]["n"] == 3


def test_judge_win_rate_excludes_inconclusive(conn: sqlite3.Connection) -> None:
    """confident=False 的不进 win_rate 统计。"""
    b1 = _seed_inspection(conn, prompt_version="v6", image_sha="a"*64)
    c1 = _seed_inspection(conn, prompt_version="v7", image_sha="a"*64)
    b2 = _seed_inspection(conn, prompt_version="v6", image_sha="b"*64)
    c2 = _seed_inspection(conn, prompt_version="v7", image_sha="b"*64)

    _seed_judgment(conn, baseline_iid=b1, candidate_iid=c1, image_sha="a"*64, winner="candidate")
    _seed_judgment(conn, baseline_iid=b2, candidate_iid=c2, image_sha="b"*64, confident=False)

    result = trend(conn, metric="judge_win_rate", group_by="prompt_version")
    by_group = {s["group"]: s for s in result["series"]}
    assert by_group["v7"]["n"] == 1  # 只有 1 个 confident
    assert by_group["v7"]["value"] == 1.0


# === 错误处理 ===


def test_invalid_metric_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        trend(conn, metric="garbage", group_by="prompt_version")  # type: ignore[arg-type]


def test_invalid_group_by_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        trend(conn, metric="p50_latency", group_by="garbage")  # type: ignore[arg-type]


def test_empty_db_returns_empty_series(conn: sqlite3.Connection) -> None:
    result = trend(conn, metric="p50_latency", group_by="prompt_version")
    assert result["series"] == []


def test_failed_inspections_excluded_from_p50(conn: sqlite3.Connection) -> None:
    """status=failed 的不进 p50_latency 统计（只看成功样本的性能）。"""
    _seed_inspection(conn, prompt_version="x", elapsed_ms=100000, image_sha="a"*64, status="succeeded")
    # 失败的不算
    iid = inspection_repo.create(conn, image_path="/tmp/x.jpg", schema_version="v2")
    metrics_repo.record_failure(
        conn,
        iid,
        version=VersionFingerprint(api_version="v2", prompt_version="x", model="x"),
        inp=InputFingerprint(image_sha256="b"*64, image_bytes=1),
        runtime=RuntimeMetrics(total_elapsed_ms=999999),
        status="failed",
        error_code="X",
    )

    result = trend(conn, metric="p50_latency", group_by="prompt_version")
    assert result["series"][0]["value"] == 100000.0
    assert result["series"][0]["n"] == 1


def test_default_since_is_30_days_ago(conn: sqlite3.Connection) -> None:
    """since=None 时默认 30 天前 —— 太老的数据不进。"""
    result = trend(conn, metric="p50_latency", group_by="prompt_version", since=None)
    since = result["since"]
    # 应当是 ISO 字符串
    parsed = datetime.fromisoformat(since.replace("Z", "+00:00"))
    expected = datetime.now(UTC) - timedelta(days=30)
    # 允许 1 分钟误差（测试运行需要时间）
    assert abs((parsed - expected).total_seconds()) < 60


# === 健全性：枚举常量与实现对齐 ===


def test_all_valid_metrics_are_implemented(conn: sqlite3.Connection) -> None:
    """新增 metric 时必须同步实现 —— 任一不工作即破契约。"""
    for m in VALID_METRICS:
        result = trend(conn, metric=m, group_by="prompt_version")
        assert result["metric"] == m


def test_all_valid_group_bys_are_implemented(conn: sqlite3.Connection) -> None:
    for g in VALID_GROUP_BYS:
        result = trend(conn, metric="finding_count", group_by=g)
        assert result["group_by"] == g
