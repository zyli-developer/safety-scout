"""v2 端到端真实 smoke —— 跑一张 fixture 图，确认 Agent SDK 全链路工作。

用法：
    uv run python scripts/v2_smoke.py [case_id]
    uv run python scripts/v2_smoke.py 1            # case_001
    uv run python scripts/v2_smoke.py case_002

会真实调 Claude，消耗订阅额度。失败时打详细错误，便于定位是 SDK、image read
还是 tool 调度问题。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# 让脚本能 import app.*（不走 uv 包安装）
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.config import Settings  # noqa: E402
from app.errors import LLMCallError, LLMTimeoutError  # noqa: E402
from app.safety_agent.agent import analyze_image  # noqa: E402
from app.safety_agent.loader import SkillLoader  # noqa: E402

REPO_ROOT = _BACKEND.parent
FIXTURES_IMG = _BACKEND / "tests" / "fixtures" / "images"
SKILLS_ROOT = REPO_ROOT / "safety_skills"


def _resolve_image(case: str) -> Path:
    """允许传 '1' / '001' / 'case_001' / 完整文件名。"""
    if Path(case).is_file():
        return Path(case)
    case = case.lower().replace("case_", "").lstrip("0") or "1"
    for p in sorted(FIXTURES_IMG.glob("case_*.jpg")):
        idx = int(p.name.split("_", 2)[1])
        if str(idx) == case:
            return p
    raise SystemExit(f"找不到 case {case!r}；可用：{sorted(p.name for p in FIXTURES_IMG.glob('case_*.jpg'))}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", nargs="?", default="1", help="case id or image path")
    parser.add_argument("--timeout", type=int, default=120, help="agent timeout s")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # claude_agent_sdk 的内部日志太啰嗦，压一压
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
    # 想看 agent 内部决策的，把这个调成 DEBUG（_drain 里有结构化埋点）
    logging.getLogger("app.safety_agent").setLevel(logging.INFO)

    image_path = _resolve_image(args.case)
    print(f"image: {image_path}")
    image_bytes = image_path.read_bytes()
    print(f"size: {len(image_bytes)} bytes")

    settings = Settings(
        safety_skills_root=SKILLS_ROOT,
        agent_timeout_seconds=args.timeout,
    )
    loader = SkillLoader(SKILLS_ROOT)

    t0 = time.monotonic()
    try:
        report, stats = await analyze_image(
            image_bytes=image_bytes,
            settings=settings,
            skill_loader=loader,
        )
    except LLMTimeoutError as exc:
        print(f"[TIMEOUT] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except LLMCallError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(3) from exc

    elapsed = time.monotonic() - t0
    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"elapsed: {elapsed:.1f}s   tool_calls: {stats.tool_calls}   "
          f"scenarios: {stats.scenarios_loaded}")
    print(f"tokens: input={stats.input_tokens} output={stats.output_tokens}   "
          f"cost: ${stats.cost_usd:.4f}")
    print()
    print(f"image_summary:    {report.report_meta.image_summary}")
    print(f"scene_detected:   {report.report_meta.scene_detected}")
    print(f"overall_risk:     {report.report_meta.overall_risk_level}")
    print(f"analysis_conf:    {report.report_meta.analysis_confidence}")
    print()
    print(f"findings: {len(report.findings)}")
    for f in report.findings:
        print(f"  [{f.severity}] {f.check_id} {f.title}")
        print(f"     位置: {f.location}")
        print(f"     依据: {f.regulation}")
        print(f"     行动: {f.action}")
    print(f"\nno_findings: {len(report.no_findings)}; uncertain: {len(report.uncertain)}")
    print(f"summary: {report.summary.model_dump_json(indent=2)}")

    # 落盘原始 JSON，便于人工对比
    out = _BACKEND / "scripts" / "_v2_smoke_last.json"
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
