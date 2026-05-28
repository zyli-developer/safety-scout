"""inspection_metrics → CSV 导出器（docs/specs/quality-tracking.md §3.4）。

用法：
    uv run python scripts/dump_metrics.py [-o out.csv]
    uv run python scripts/dump_metrics.py --since 2026-05-01 --prompt-version v7
    uv run python scripts/dump_metrics.py --status failed --since 2026-05-20
    uv run python scripts/dump_metrics.py --image-sha <sha256> -o repeats.csv

设计：
- 全列输出 —— 用户用 excel 自己切，不在脚本里做聚合
- 加两个 derived 列（latency_seconds / tokens_per_finding）方便 excel pivot
- 失败行也输出（status=failed/timeout），与 metrics_repo.record_failure 对应
- 默认 stdout，给 -o 才落盘

测试入口：tests/unit/test_dump_metrics_script.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.config import get_settings  # noqa: E402
from app.storage import metrics_repo  # noqa: E402
from app.storage.db import connect  # noqa: E402

# CSV 列顺序 —— 优先放识别 + 版本指纹，再放性能 + 结果形状，最后状态。
COLUMNS = [
    # 标识
    "inspection_id",
    "recorded_at",
    "status",
    "error_code",
    # 版本指纹
    "api_version",
    "prompt_version",
    "skill_index_version",
    "model",
    # 输入指纹
    "image_sha256",
    "image_bytes",
    "run_group_id",
    # 性能（含 derived）
    "total_elapsed_ms",
    "latency_seconds",  # derived = total_elapsed_ms / 1000
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "cost_usd",
    "tool_calls",
    "scenarios_loaded",
    "tool_call_timings_json",
    # 结果形状（含 derived）
    "finding_count",
    "no_finding_count",
    "uncertain_count",
    "tokens_per_finding",  # derived = output_tokens / max(finding_count,1)
    "severity_dist_json",
    "is_major_count",
    "major_basis_filled_count",
    "reg_coverage",
]


def _enrich(row: dict) -> dict:
    """加 derived 列（latency_seconds / tokens_per_finding）。"""
    elapsed_ms = row.get("total_elapsed_ms") or 0
    out_tok = row.get("output_tokens") or 0
    findings = row.get("finding_count") or 0
    row["latency_seconds"] = round(elapsed_ms / 1000.0, 2) if elapsed_ms else None
    # 0 findings 时不算（避免分母为 0；用 None 而非 inf 让 excel 不显示数字）
    row["tokens_per_finding"] = round(out_tok / findings, 1) if findings > 0 else None
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 inspection_metrics 为 CSV")
    parser.add_argument("--since", help="recorded_at >= ISO8601, 如 2026-05-01")
    parser.add_argument("--until", help="recorded_at < ISO8601")
    parser.add_argument("--prompt-version", help="过滤 prompt_version (如 v7 / 1.0.0)")
    parser.add_argument(
        "--status",
        choices=["succeeded", "failed", "timeout"],
        help="过滤 status；不传 = 全部（含失败/超时）",
    )
    parser.add_argument("--image-sha", help="过滤 image_sha256（同图复跑分析用）")
    parser.add_argument("--limit", type=int, help="最多 N 行；默认全部")
    parser.add_argument(
        "-o",
        "--output",
        help="输出 CSV 文件路径；不传 = stdout",
    )
    parser.add_argument(
        "--db",
        help="覆盖 SQLite 路径；默认从 Settings 取（local_data/safety_scout.db）",
    )
    args = parser.parse_args()

    db_path = args.db or get_settings().sqlite_path
    if not Path(db_path).exists():
        print(f"[error] DB 不存在: {db_path}", file=sys.stderr)
        return 2

    conn = connect(db_path)
    try:
        rows = metrics_repo.query(
            conn,
            since=args.since,
            until=args.until,
            prompt_version=args.prompt_version,
            status=args.status,
            image_sha256=args.image_sha,
            limit=args.limit,
        )
    finally:
        conn.close()

    if not rows:
        print("[warn] 0 行匹配", file=sys.stderr)
        return 0

    # 输出 sink：stdout 或文件
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sink = out_path.open("w", newline="", encoding="utf-8")
    else:
        sink = sys.stdout

    try:
        writer = csv.DictWriter(sink, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(_enrich(r))
    finally:
        if args.output:
            sink.close()
            print(f"wrote {len(rows)} rows → {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
