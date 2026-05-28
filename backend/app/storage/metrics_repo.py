"""inspection_metrics 表 CRUD —— 质量追踪 Layer 1。

设计契约（docs/specs/quality-tracking.md §3）：
- 每次分析（含失败 / 超时）写一行 —— 防幸存者偏差
- `record_from_report` 负责把 ReportPayload / ReportV2Payload 摘要成 derived 字段
  （finding_count / severity_dist_json / reg_coverage / is_major_count 等），
  调用方不用关心 schema 差异
- `record_failure` 负责失败 / 超时路径（没有 report 可摘）

测试入口：tests/unit/test_metrics_repo.py
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.schemas.report import ReportPayload
from app.schemas.report_v2 import ReportV2Payload

ApiVersion = Literal["v1", "v2"]
MetricStatus = Literal["succeeded", "failed", "timeout"]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class RuntimeMetrics:
    """运行期采集到的指标（service 层在调 record_* 时填）。"""

    total_elapsed_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
    scenarios_loaded: list[str] | None = None
    # 每次 tool dispatch 的轻量轨迹（agent 层填）：
    #   [{"seq":1,"name":"load_scenario_skill","scenario_id":"S05","dispatched_ms":1500}, ...]
    # 同一 AssistantMessage 内的多个 ToolUseBlock 共享 dispatched_ms（SDK 一帧批发）。
    # 事后 duration_ms = 下一条 dispatched_ms - 当前；最后一条 = total_elapsed_ms - 当前。
    tool_call_timings: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class VersionFingerprint:
    """版本指纹 —— 缺这个就无法 group_by 比较两个 prompt 改动孰优孰劣。"""

    api_version: ApiVersion
    prompt_version: str
    model: str
    skill_index_version: str | None = None


@dataclass(frozen=True)
class InputFingerprint:
    """输入指纹 —— image_sha256 用于同图复跑算方差。"""

    image_sha256: str
    image_bytes: int
    run_group_id: str | None = None


# -------------- 摘要派生（report → derived 字段） --------------


def _summarize_v1(report: ReportPayload) -> dict[str, Any]:
    """v1 ReportPayload → derived 字段 dict。"""
    hazards = report.hazards
    dist = {"high": 0, "medium": 0, "low": 0}
    reg_count = 0
    is_major = 0
    major_basis_filled = 0
    for h in hazards:
        dist[h.severity] = dist.get(h.severity, 0) + 1
        if h.regulation:
            reg_count += 1
        if h.is_major:
            is_major += 1
            if h.major_basis:
                major_basis_filled += 1
    return {
        "finding_count": len(hazards),
        "no_finding_count": 0,
        "uncertain_count": 0,
        "severity_dist_json": json.dumps(dist, ensure_ascii=False),
        "is_major_count": is_major,
        "major_basis_filled_count": major_basis_filled,
        "reg_coverage": (reg_count / len(hazards)) if hazards else 0.0,
    }


def _summarize_v2(report: ReportV2Payload) -> dict[str, Any]:
    """v2 ReportV2Payload → derived 字段 dict。"""
    findings = report.findings
    dist = {"重大": 0, "较大": 0, "一般": 0, "低": 0}
    reg_count = 0
    is_major = 0
    major_basis_filled = 0
    for f in findings:
        dist[f.severity] = dist.get(f.severity, 0) + 1
        if f.regulation:
            reg_count += 1
        if f.is_major:
            is_major += 1
            if f.major_basis:
                major_basis_filled += 1
    return {
        "finding_count": len(findings),
        "no_finding_count": len(report.no_findings),
        "uncertain_count": len(report.uncertain),
        "severity_dist_json": json.dumps(dist, ensure_ascii=False),
        "is_major_count": is_major,
        "major_basis_filled_count": major_basis_filled,
        "reg_coverage": (reg_count / len(findings)) if findings else 0.0,
    }


# -------------- 写入入口 --------------


def record_from_report(
    conn: sqlite3.Connection,
    inspection_id: str,
    *,
    version: VersionFingerprint,
    inp: InputFingerprint,
    runtime: RuntimeMetrics,
    report: ReportPayload | ReportV2Payload,
    status: MetricStatus = "succeeded",
) -> None:
    """成功路径 —— 把 report 摘要为 derived 字段后写入。

    v1 走 ReportPayload 分支，v2 走 ReportV2Payload 分支；类型决定 summary 函数。
    重复写入同一 inspection_id 会触发 PRIMARY KEY 冲突（异常上抛，调用方决定怎么办）。
    """
    if isinstance(report, ReportV2Payload):
        derived = _summarize_v2(report)
    else:
        derived = _summarize_v1(report)
    _insert(
        conn,
        inspection_id=inspection_id,
        version=version,
        inp=inp,
        runtime=runtime,
        derived=derived,
        status=status,
        error_code=None,
    )


def record_failure(
    conn: sqlite3.Connection,
    inspection_id: str,
    *,
    version: VersionFingerprint,
    inp: InputFingerprint,
    runtime: RuntimeMetrics,
    status: MetricStatus,
    error_code: str | None,
) -> None:
    """失败 / 超时路径 —— 没有 report 可摘，但仍要写一行（防幸存者偏差）。"""
    assert status in ("failed", "timeout"), "record_failure 仅用于失败 / 超时"
    derived = {
        "finding_count": 0,
        "no_finding_count": 0,
        "uncertain_count": 0,
        "severity_dist_json": None,
        "is_major_count": 0,
        "major_basis_filled_count": 0,
        "reg_coverage": None,
    }
    _insert(
        conn,
        inspection_id=inspection_id,
        version=version,
        inp=inp,
        runtime=runtime,
        derived=derived,
        status=status,
        error_code=error_code,
    )


def _insert(
    conn: sqlite3.Connection,
    *,
    inspection_id: str,
    version: VersionFingerprint,
    inp: InputFingerprint,
    runtime: RuntimeMetrics,
    derived: dict[str, Any],
    status: MetricStatus,
    error_code: str | None,
) -> None:
    scenarios_json = (
        json.dumps(runtime.scenarios_loaded, ensure_ascii=False)
        if runtime.scenarios_loaded is not None
        else "[]"
    )
    timings_json = (
        json.dumps(runtime.tool_call_timings, ensure_ascii=False)
        if runtime.tool_call_timings
        else None
    )
    conn.execute(
        """
        INSERT INTO inspection_metrics (
            inspection_id, api_version, prompt_version, skill_index_version, model,
            image_sha256, image_bytes, run_group_id,
            total_elapsed_ms, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd,
            tool_calls, scenarios_loaded, tool_call_timings_json,
            finding_count, no_finding_count, uncertain_count, severity_dist_json,
            is_major_count, major_basis_filled_count, reg_coverage,
            status, error_code, recorded_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        )
        """,
        (
            inspection_id,
            version.api_version,
            version.prompt_version,
            version.skill_index_version,
            version.model,
            inp.image_sha256,
            inp.image_bytes,
            inp.run_group_id,
            runtime.total_elapsed_ms,
            runtime.input_tokens,
            runtime.output_tokens,
            runtime.cache_read_tokens,
            runtime.cache_creation_tokens,
            runtime.cost_usd,
            runtime.tool_calls,
            scenarios_json,
            timings_json,
            derived["finding_count"],
            derived["no_finding_count"],
            derived["uncertain_count"],
            derived["severity_dist_json"],
            derived["is_major_count"],
            derived["major_basis_filled_count"],
            derived["reg_coverage"],
            status,
            error_code,
            _now_iso(),
        ),
    )
    conn.commit()


# -------------- 查询入口 --------------


def get(conn: sqlite3.Connection, inspection_id: str) -> dict[str, Any] | None:
    """单条 metrics 行 —— 主要给单测查证写入用。"""
    row = conn.execute(
        "SELECT * FROM inspection_metrics WHERE inspection_id = ?",
        (inspection_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def query(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    until: str | None = None,
    prompt_version: str | None = None,
    status: MetricStatus | None = None,
    image_sha256: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """按过滤条件查 metrics。给 dump_metrics.py CLI / quality_trend service 用。

    全部参数都是 optional；不传即不过滤。按 recorded_at DESC 排序。
    """
    sql = "SELECT * FROM inspection_metrics WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        sql += " AND recorded_at >= ?"
        params.append(since)
    if until is not None:
        sql += " AND recorded_at < ?"
        params.append(until)
    if prompt_version is not None:
        sql += " AND prompt_version = ?"
        params.append(prompt_version)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    if image_sha256 is not None:
        sql += " AND image_sha256 = ?"
        params.append(image_sha256)
    sql += " ORDER BY recorded_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
