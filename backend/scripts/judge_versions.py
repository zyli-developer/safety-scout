"""LLM-as-Judge A/B 评判 CLI（docs/specs/quality-tracking.md §4.5）。

把数据库里两组（baseline / candidate）分析结果按 image_sha256 join 起来，
对每对 (baseline_inspection, candidate_inspection) 跑一次 pairwise judge（含位置去偏），
把 verdict 写入 quality_judgments，最后输出 ACCEPT / REJECT 判定表。

用法：
    # 按 prompt_version 选两组（最常见）
    uv run python scripts/judge_versions.py \\
        --baseline-prompt 1.0.0 --candidate-prompt 1.1.0 \\
        --judge-model claude-sonnet-4-5

    # 按 inspection_id 列表显式指定
    uv run python scripts/judge_versions.py \\
        --baseline-ids abc,def --candidate-ids ghi,jkl

注意：需要数据库里**两组都对同一些 image_sha256 跑过**才能配对评判。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sqlite3
import sys
from pathlib import Path
from statistics import median

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.config import get_settings  # noqa: E402
from app.llm.claude_cli import ClaudeCLIProvider  # noqa: E402
from app.quality.accept_rules import evaluate  # noqa: E402
from app.quality.judge_service import judge_pair  # noqa: E402
from app.storage import inspection_repo, judgments_repo, metrics_repo  # noqa: E402
from app.storage.db import connect  # noqa: E402

logger = logging.getLogger(__name__)


def _select_inspection_ids(
    conn: sqlite3.Connection,
    *,
    prompt_version: str | None,
    explicit_ids: list[str] | None,
) -> list[dict]:
    """选出一组 metrics rows（含 image_sha256 + inspection_id）。"""
    if explicit_ids:
        rows: list[dict] = []
        for iid in explicit_ids:
            m = metrics_repo.get(conn, iid)
            if m is not None:
                rows.append(m)
        return rows
    if prompt_version:
        return metrics_repo.query(conn, prompt_version=prompt_version, status="succeeded")
    raise SystemExit("必须传 --baseline-prompt 或 --baseline-ids 之一（candidate 同）")


def _pair_by_image(
    baseline_rows: list[dict], candidate_rows: list[dict]
) -> list[tuple[dict, dict]]:
    """按 image_sha256 配对 —— 同图才能 pairwise 比较。

    若一组里同图有多次跑（self-consistency），按 recorded_at 最新的取一份。
    """
    by_sha_b = {}
    for r in sorted(baseline_rows, key=lambda x: x["recorded_at"], reverse=True):
        by_sha_b.setdefault(r["image_sha256"], r)
    by_sha_c = {}
    for r in sorted(candidate_rows, key=lambda x: x["recorded_at"], reverse=True):
        by_sha_c.setdefault(r["image_sha256"], r)

    pairs = []
    for sha, b in by_sha_b.items():
        if sha in by_sha_c:
            pairs.append((b, by_sha_c[sha]))
    return pairs


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    db_path = args.db or settings.sqlite_path
    if not Path(db_path).exists():
        print(f"[error] DB 不存在: {db_path}", file=sys.stderr)
        return 2

    conn = connect(db_path)
    try:
        baseline_rows = _select_inspection_ids(
            conn,
            prompt_version=args.baseline_prompt,
            explicit_ids=args.baseline_ids.split(",") if args.baseline_ids else None,
        )
        candidate_rows = _select_inspection_ids(
            conn,
            prompt_version=args.candidate_prompt,
            explicit_ids=args.candidate_ids.split(",") if args.candidate_ids else None,
        )
        if not baseline_rows:
            print("[error] baseline 组为空", file=sys.stderr)
            return 2
        if not candidate_rows:
            print("[error] candidate 组为空", file=sys.stderr)
            return 2

        pairs = _pair_by_image(baseline_rows, candidate_rows)
        if not pairs:
            print(
                "[error] 两组没有共同的 image_sha256 —— 无法配对评判。"
                "请确保两组都对同一些图跑过分析。",
                file=sys.stderr,
            )
            return 2

        print(
            f"配对：baseline {len(baseline_rows)} 行 × candidate {len(candidate_rows)} 行 "
            f"→ {len(pairs)} 对（按 image_sha256 join）"
        )

        # 构造 judge_call：用 Claude CLI provider 跑 judge_model（doc §4.3）
        judge_provider = ClaudeCLIProvider(
            cli_path=settings.claude_cli_path,
            model=args.judge_model,
            timeout_seconds=settings.judge_timeout_seconds,
        )

        async def judge_call(prompt: str) -> str:
            # judge prompt 不含图片 —— 我们把 base64 图片塞 prompt 不实际，
            # judge 只看两份 JSON report 即可（rubric 已规定 judge 不依赖图片像素）。
            raw = await judge_provider.analyze(b"", prompt)
            return raw.content

        # 跑配对评判
        for i, (b_row, c_row) in enumerate(pairs, 1):
            print(
                f"\n[{i}/{len(pairs)}] image={b_row['image_sha256'][:8]} "
                f"baseline={b_row['inspection_id'][:8]} vs candidate={c_row['inspection_id'][:8]}"
            )
            b_insp = inspection_repo.get(conn, b_row["inspection_id"])
            c_insp = inspection_repo.get(conn, c_row["inspection_id"])
            if (
                b_insp is None or c_insp is None
                or b_insp.report_json is None or c_insp.report_json is None
            ):
                print("  跳过：报告 JSON 缺失")
                continue

            verdict = await judge_pair(
                judge_call=judge_call,
                judge_model=args.judge_model,
                baseline_report_json=b_insp.report_json,
                candidate_report_json=c_insp.report_json,
                baseline_inspection_id=b_row["inspection_id"],
                candidate_inspection_id=c_row["inspection_id"],
            )
            judgments_repo.record(conn, verdict, image_sha256=b_row["image_sha256"])
            print(
                f"  → confident={verdict.confident}  overall={verdict.winner_overall}  "
                f"summary: {verdict.overall_summary or '(inconclusive)'}"
            )

        # 聚合 + accept rules
        agg = judgments_repo.aggregate_win_rate(
            conn, judge_model=args.judge_model
        )
        # 性能 gate 数据：取两组的 p50 latency
        b_p50 = (
            median(r["total_elapsed_ms"] for r in baseline_rows if r["total_elapsed_ms"])
            if baseline_rows else None
        )
        c_p50 = (
            median(r["total_elapsed_ms"] for r in candidate_rows if r["total_elapsed_ms"])
            if candidate_rows else None
        )
        report = evaluate(
            overall_counts=agg["overall"],
            recall_counts=agg["recall"],
            precision_counts=agg["precision"],
            inconclusive=agg["inconclusive"],
            confident=agg["confident"],
            baseline_p50_latency_ms=b_p50,
            candidate_p50_latency_ms=c_p50,
        )

        _print_summary(agg, report, b_p50, c_p50)
        return 0 if report.verdict == "ACCEPT" else 1
    finally:
        conn.close()


def _print_summary(agg: dict, report, b_p50, c_p50) -> None:
    print("\n" + "=" * 70)
    print("Judge Verdict")
    print("=" * 70)
    print(f"Total judged: {agg['total']}  confident: {agg['confident']}  inconclusive: {agg['inconclusive']}")
    print(
        f"  overall:    candidate={agg['overall']['candidate']:>3}  "
        f"baseline={agg['overall']['baseline']:>3}  tie={agg['overall']['tie']:>3}"
    )
    for dim in ("recall", "precision", "regulation", "action"):
        c = agg[dim]
        print(
            f"  {dim:<10} candidate={c['candidate']:>3}  "
            f"baseline={c['baseline']:>3}  tie={c['tie']:>3}"
        )
    if b_p50 is not None and c_p50 is not None:
        print(f"\nLatency p50: baseline={b_p50:.0f}ms  candidate={c_p50:.0f}ms")

    print("\nGate checks:")
    for g in report.gates:
        mark = "✓" if g.passed else "✗"
        print(f"  [{mark}] {g.name}: {g.detail}")
    print(f"\nVerdict: {'✅ ACCEPT' if report.verdict == 'ACCEPT' else '⚠️  REJECT'}")
    if report.verdict == "REJECT":
        print("失败 gate:")
        for g in report.failed_gates():
            print(f"  - {g.name}: {g.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM-as-Judge A/B 评判（docs/specs/quality-tracking.md §4）"
    )
    g_base = parser.add_argument_group("baseline 组（二选一）")
    g_base.add_argument("--baseline-prompt", help="prompt_version 字符串过滤")
    g_base.add_argument("--baseline-ids", help="逗号分隔的 inspection_id 列表")
    g_cand = parser.add_argument_group("candidate 组（二选一）")
    g_cand.add_argument("--candidate-prompt")
    g_cand.add_argument("--candidate-ids")
    parser.add_argument(
        "--judge-model",
        default=None,
        help="judge LLM 模型；默认取 Settings.judge_model (sonnet-4-5)",
    )
    parser.add_argument(
        "--db", help="覆盖 SQLite 路径（默认从 Settings 取）"
    )
    args = parser.parse_args()

    if args.judge_model is None:
        args.judge_model = get_settings().judge_model

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("anyio").setLevel(logging.WARNING)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
