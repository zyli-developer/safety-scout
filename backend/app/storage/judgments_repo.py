"""quality_judgments 表 CRUD —— 质量追踪 Layer 2。

写入：判定服务 `app.quality.judge_service.judge_pair` 完成后直接 record。
查询：`query` / `aggregate_win_rate` 给 `judge_versions.py` 和 `quality_trend` service 用。
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from app.quality.judge_service import PairVerdict


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(
    conn: sqlite3.Connection, verdict: PairVerdict, *, image_sha256: str
) -> None:
    """把一次 judge_pair 的结果写入 quality_judgments。

    `confident=False`（inconclusive）也要写 —— 用于统计 judge 稳定性。
    """
    conn.execute(
        """
        INSERT INTO quality_judgments (
            id, image_sha256, baseline_inspection_id, candidate_inspection_id,
            judge_model, judge_rubric_version, confident,
            winner_overall, winner_recall, winner_precision, winner_regulation, winner_action,
            judge_confidence, overall_summary,
            raw_json_1, raw_json_2, cost_usd, judged_at
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?
        )
        """,
        (
            verdict.id,
            image_sha256,
            verdict.baseline_inspection_id,
            verdict.candidate_inspection_id,
            verdict.judge_model,
            verdict.judge_rubric_version,
            1 if verdict.confident else 0,
            verdict.winner_overall,
            verdict.winner_recall,
            verdict.winner_precision,
            verdict.winner_regulation,
            verdict.winner_action,
            verdict.confidence_self,
            verdict.overall_summary,
            verdict.raw_json_1,
            verdict.raw_json_2,
            verdict.cost_usd,
            _now_iso(),
        ),
    )
    conn.commit()


def get(conn: sqlite3.Connection, judgment_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM quality_judgments WHERE id = ?", (judgment_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def query(
    conn: sqlite3.Connection,
    *,
    image_sha256: str | None = None,
    judge_model: str | None = None,
    only_confident: bool = False,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """按过滤条件查 judgments。`only_confident=True` 排除 inconclusive。"""
    sql = "SELECT * FROM quality_judgments WHERE 1=1"
    params: list[Any] = []
    if image_sha256 is not None:
        sql += " AND image_sha256 = ?"
        params.append(image_sha256)
    if judge_model is not None:
        sql += " AND judge_model = ?"
        params.append(judge_model)
    if only_confident:
        sql += " AND confident = 1"
    if since is not None:
        sql += " AND judged_at >= ?"
        params.append(since)
    sql += " ORDER BY judged_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def aggregate_win_rate(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    judge_model: str | None = None,
) -> dict[str, Any]:
    """聚合 baseline vs candidate 的 win/tie/loss 计数 + 4 维度细分。

    只统计 confident=1 的 verdict（inconclusive 单独计数）。
    返回 dict 给 dashboard / CLI 直接消费。
    """
    sql_base = "FROM quality_judgments WHERE 1=1"
    params: list[Any] = []
    if since:
        sql_base += " AND judged_at >= ?"
        params.append(since)
    if judge_model:
        sql_base += " AND judge_model = ?"
        params.append(judge_model)

    # 总数（含 inconclusive）
    total = conn.execute(f"SELECT COUNT(*) {sql_base}", params).fetchone()[0]
    inconclusive = conn.execute(
        f"SELECT COUNT(*) {sql_base} AND confident = 0", params
    ).fetchone()[0]

    # 各维度 winner 计数（仅 confident=1）
    sql_conf = f"{sql_base} AND confident = 1"

    def _counts(col: str) -> dict[str, int]:
        rows = conn.execute(
            f"SELECT {col} AS w, COUNT(*) AS n {sql_conf} GROUP BY {col}", params
        ).fetchall()
        d = {"baseline": 0, "candidate": 0, "tie": 0}
        for r in rows:
            if r["w"] in d:
                d[r["w"]] = r["n"]
        return d

    return {
        "total": total,
        "inconclusive": inconclusive,
        "confident": total - inconclusive,
        "overall": _counts("winner_overall"),
        "recall": _counts("winner_recall"),
        "precision": _counts("winner_precision"),
        "regulation": _counts("winner_regulation"),
        "action": _counts("winner_action"),
    }
