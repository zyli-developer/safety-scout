"""质量趋势聚合服务 —— Layer 3 数据接口（docs/specs/quality-tracking.md §5）。

把 inspection_metrics + quality_judgments 聚合成 (group, x, value, n) 序列，
给 GET /api/v1/quality/trend 用。

矩阵：
    metric × group_by
    - judge_win_rate     × prompt_version | model | day
    - p50_latency        × prompt_version | model | day
    - output_tokens      × prompt_version | model | day
    - finding_count      × prompt_version | model | day
    - reg_coverage       × prompt_version | model | day

实现细节：
- p50 在 Python 端排序后取中位（SQLite 没原生 PERCENTILE_CONT）
- judge_win_rate 是 confident verdict 里 candidate winner 占比，按 candidate
  inspection 的 prompt_version 分组
- since=None 时默认 30 天前
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any, Literal

Metric = Literal[
    "judge_win_rate",
    "p50_latency",
    "output_tokens",
    "finding_count",
    "reg_coverage",
]
GroupBy = Literal["prompt_version", "model", "day"]

VALID_METRICS: tuple[Metric, ...] = (
    "judge_win_rate",
    "p50_latency",
    "output_tokens",
    "finding_count",
    "reg_coverage",
)
VALID_GROUP_BYS: tuple[GroupBy, ...] = ("prompt_version", "model", "day")


def _default_since() -> str:
    return (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bucket_x(row: dict, group_by: GroupBy) -> str:
    """按 group_by 维度算 row 的桶值。"""
    if group_by == "prompt_version":
        return row.get("prompt_version") or "unknown"
    if group_by == "model":
        return row.get("model") or "unknown"
    if group_by == "day":
        # recorded_at 截取 YYYY-MM-DD
        ts = row.get("recorded_at") or ""
        return ts[:10]
    raise ValueError(f"unknown group_by: {group_by}")


def _aggregate_simple(
    rows: list[dict], group_by: GroupBy, value_col: str, agg: str = "median"
) -> list[dict[str, Any]]:
    """按 group 桶聚合数值列（agg='median' 或 'mean'）。

    None 值跳过（不参与聚合）；空桶不出现在结果里。
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        v = r.get(value_col)
        if v is None:
            continue
        buckets[_bucket_x(r, group_by)].append(float(v))

    series: list[dict[str, Any]] = []
    for key, vals in buckets.items():
        if not vals:
            continue
        agg_val = median(vals) if agg == "median" else sum(vals) / len(vals)
        series.append({"group": key, "x": key, "value": round(agg_val, 4), "n": len(vals)})
    # 按 group 字典序稳定排序
    series.sort(key=lambda d: d["group"])
    return series


def _aggregate_judge_win_rate(
    conn: sqlite3.Connection,
    *,
    group_by: GroupBy,
    since: str,
) -> list[dict[str, Any]]:
    """judge_win_rate = candidate winner 在 confident verdict 中的占比。

    按 candidate_inspection 的 prompt_version / model / day 分桶。
    """
    sql = """
        SELECT q.winner_overall,
               m.prompt_version, m.model, m.recorded_at
        FROM quality_judgments q
        LEFT JOIN inspection_metrics m
          ON m.inspection_id = q.candidate_inspection_id
        WHERE q.confident = 1
          AND q.judged_at >= ?
    """
    rows = [dict(r) for r in conn.execute(sql, (since,)).fetchall()]

    # 每个桶：candidate 数 + total 数
    by_bucket: dict[str, dict[str, int]] = defaultdict(lambda: {"win": 0, "total": 0})
    for r in rows:
        bucket = _bucket_x(r, group_by) if r.get("recorded_at") else "unknown"
        by_bucket[bucket]["total"] += 1
        if r["winner_overall"] == "candidate":
            by_bucket[bucket]["win"] += 1

    series: list[dict[str, Any]] = []
    for key, c in by_bucket.items():
        if c["total"] == 0:
            continue
        series.append(
            {
                "group": key,
                "x": key,
                "value": round(c["win"] / c["total"], 4),
                "n": c["total"],
            }
        )
    series.sort(key=lambda d: d["group"])
    return series


def trend(
    conn: sqlite3.Connection,
    *,
    metric: Metric,
    group_by: GroupBy,
    since: str | None = None,
) -> dict[str, Any]:
    """计算指定 metric × group_by 的趋势序列。

    Returns:
        {"metric": ..., "group_by": ..., "since": ..., "series": [...]}
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"metric 非法: {metric}")
    if group_by not in VALID_GROUP_BYS:
        raise ValueError(f"group_by 非法: {group_by}")

    since_iso = since or _default_since()

    if metric == "judge_win_rate":
        series = _aggregate_judge_win_rate(conn, group_by=group_by, since=since_iso)
    else:
        # 其它 metric 走 inspection_metrics 直接聚合
        col_map = {
            "p50_latency": "total_elapsed_ms",
            "output_tokens": "output_tokens",
            "finding_count": "finding_count",
            "reg_coverage": "reg_coverage",
        }
        sql_rows = conn.execute(
            "SELECT prompt_version, model, recorded_at, "
            "total_elapsed_ms, output_tokens, finding_count, reg_coverage "
            "FROM inspection_metrics "
            "WHERE recorded_at >= ? AND status = 'succeeded'",
            (since_iso,),
        ).fetchall()
        rows = [dict(r) for r in sql_rows]
        # p50_latency 用 median；其它指标也用 median（更稳健）
        series = _aggregate_simple(rows, group_by, col_map[metric], agg="median")

    return {
        "metric": metric,
        "group_by": group_by,
        "since": since_iso,
        "series": series,
    }
