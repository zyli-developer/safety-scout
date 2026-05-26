"""v1 vs v2 A/B 对比脚本（plan §4.3）。

把 tests/fixtures/images/case_*.jpg 一张一张分别跑 v1（ClaudeCLIProvider 单轮）
和 v2（Agent SDK 多轮 + Skill），收集：

- JSON 解析率：v2 是否每次都被 ReportV2Payload 接住（v1 看 parse_report 是否成功）
- 隐患数量：v1 hazards.len vs v2 findings.len
- 是否引用规范：v1 看 hazard.regulation 非空率；v2 同字段
- 严重度分布：v1 high/medium/low 计数 vs v2 重大/较大/一般/低
- 命中场景：v2 独有，看 Agent 是否合理覆盖
- 耗时

每张图跑完落盘 `scripts/_ab_<case>_v{1,2}.json`，最后打表。

⚠️ 真实调 Claude，每张图 v1 ~60s + v2 ~250s ≈ 5min；5 张图约 25min。
   建议先用 --only case_001 跑通后再 --all。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.config import Settings  # noqa: E402
from app.errors import SafetyScoutError  # noqa: E402
from app.llm.claude_cli import ClaudeCLIProvider  # noqa: E402
from app.llm.parser import parse_report  # noqa: E402
from app.llm.prompt import ANALYZE_PROMPT  # noqa: E402
from app.safety_agent.agent import analyze_image  # noqa: E402
from app.safety_agent.loader import SkillLoader  # noqa: E402

REPO_ROOT = _BACKEND.parent
FIXTURES_IMG = _BACKEND / "tests" / "fixtures" / "images"
SKILLS_ROOT = REPO_ROOT / "safety_skills"
OUT_DIR = _BACKEND / "scripts" / "_ab_results"


@dataclass
class CaseResult:
    case: str
    image_size_kb: int

    v1_ok: bool = False
    v1_elapsed_s: float = 0.0
    v1_hazard_count: int = 0
    v1_severity_dist: dict[str, int] = field(default_factory=dict)
    v1_reg_coverage: float = 0.0  # 引用规范的 hazard 占比
    v1_overall_severity: str = ""
    v1_error: str = ""

    v2_ok: bool = False
    v2_elapsed_s: float = 0.0
    v2_finding_count: int = 0
    v2_no_finding_count: int = 0
    v2_uncertain_count: int = 0
    v2_severity_dist: dict[str, int] = field(default_factory=dict)
    v2_reg_coverage: float = 0.0
    v2_overall_risk: str = ""
    v2_scenes: list[str] = field(default_factory=list)
    v2_tool_calls: int = 0
    v2_input_tokens: int = 0
    v2_output_tokens: int = 0
    v2_cost_usd: float = 0.0
    v2_error: str = ""


async def run_v1(image_bytes: bytes, settings: Settings) -> tuple[dict, float]:
    """v1 路径：ClaudeCLIProvider 单轮 + parse_report 容错。返回 (report dict, elapsed)。"""
    provider = ClaudeCLIProvider(
        cli_path=settings.claude_cli_path,
        model=settings.claude_model,
        timeout_seconds=settings.claude_timeout_seconds,
    )
    t0 = time.monotonic()
    raw = await provider.analyze(image_bytes, ANALYZE_PROMPT)

    async def reprompt(corrective: str) -> str:
        r = await provider.analyze(image_bytes, corrective)
        return r.content

    report = await parse_report(raw.content, reprompt=reprompt)
    return report.model_dump(mode="json"), time.monotonic() - t0


async def run_v2(image_bytes: bytes, settings: Settings, loader: SkillLoader):
    """v2 路径：Agent SDK + Skill。返回 (report dict, stats dict, elapsed)。"""
    t0 = time.monotonic()
    report, stats = await analyze_image(
        image_bytes=image_bytes, settings=settings, skill_loader=loader
    )
    return (
        report.model_dump(mode="json"),
        {
            "tool_calls": stats.tool_calls,
            "scenarios_loaded": stats.scenarios_loaded,
            "input_tokens": stats.input_tokens,
            "output_tokens": stats.output_tokens,
            "cost_usd": stats.cost_usd,
        },
        time.monotonic() - t0,
    )


def _summarize_v1(report: dict) -> tuple[dict[str, int], float]:
    hazards = report.get("hazards", [])
    dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    reg_count = 0
    for h in hazards:
        sev = h.get("severity", "")
        if sev in dist:
            dist[sev] += 1
        if h.get("regulation"):
            reg_count += 1
    cov = reg_count / len(hazards) if hazards else 0.0
    return dist, cov


def _summarize_v2(report: dict) -> tuple[dict[str, int], float]:
    findings = report.get("findings", [])
    dist: dict[str, int] = {"重大": 0, "较大": 0, "一般": 0, "低": 0}
    reg_count = 0
    for f in findings:
        sev = f.get("severity", "")
        if sev in dist:
            dist[sev] += 1
        if f.get("regulation"):
            reg_count += 1
    cov = reg_count / len(findings) if findings else 0.0
    return dist, cov


async def run_case(
    image_path: Path,
    settings: Settings,
    loader: SkillLoader,
    skip_v1: bool,
    skip_v2: bool,
) -> CaseResult:
    image_bytes = image_path.read_bytes()
    result = CaseResult(
        case=image_path.stem,
        image_size_kb=len(image_bytes) // 1024,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not skip_v1:
        print(f"[{result.case}] v1 running ...")
        try:
            v1_report, v1_elapsed = await run_v1(image_bytes, settings)
            (OUT_DIR / f"{result.case}_v1.json").write_text(
                json.dumps(v1_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            dist, cov = _summarize_v1(v1_report)
            result.v1_ok = True
            result.v1_elapsed_s = v1_elapsed
            result.v1_hazard_count = len(v1_report.get("hazards", []))
            result.v1_severity_dist = dist
            result.v1_reg_coverage = cov
            result.v1_overall_severity = v1_report.get("overall_severity", "")
            print(f"  v1 ok in {v1_elapsed:.1f}s  hazards={result.v1_hazard_count}  dist={dist}")
        except (SafetyScoutError, Exception) as exc:  # noqa: BLE001
            result.v1_error = f"{type(exc).__name__}: {exc}"
            print(f"  v1 FAIL: {result.v1_error}")

    if not skip_v2:
        print(f"[{result.case}] v2 running ...")
        try:
            v2_report, v2_stats, v2_elapsed = await run_v2(image_bytes, settings, loader)
            (OUT_DIR / f"{result.case}_v2.json").write_text(
                json.dumps(v2_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            dist, cov = _summarize_v2(v2_report)
            result.v2_ok = True
            result.v2_elapsed_s = v2_elapsed
            result.v2_finding_count = len(v2_report.get("findings", []))
            result.v2_no_finding_count = len(v2_report.get("no_findings", []))
            result.v2_uncertain_count = len(v2_report.get("uncertain", []))
            result.v2_severity_dist = dist
            result.v2_reg_coverage = cov
            result.v2_overall_risk = v2_report["report_meta"]["overall_risk_level"]
            result.v2_scenes = v2_report["report_meta"]["scene_detected"]
            result.v2_tool_calls = v2_stats["tool_calls"]
            result.v2_input_tokens = v2_stats["input_tokens"]
            result.v2_output_tokens = v2_stats["output_tokens"]
            result.v2_cost_usd = v2_stats["cost_usd"]
            print(
                f"  v2 ok in {v2_elapsed:.1f}s  findings={result.v2_finding_count}  "
                f"uncertain={result.v2_uncertain_count}  scenes={result.v2_scenes}  dist={dist}"
            )
        except (SafetyScoutError, Exception) as exc:  # noqa: BLE001
            result.v2_error = f"{type(exc).__name__}: {exc}"
            print(f"  v2 FAIL: {result.v2_error}")
            traceback.print_exc()

    return result


def print_summary(results: list[CaseResult]) -> None:
    print()
    print("=" * 100)
    print(f"{'case':<55} {'v1':<22} {'v2':<22}")
    print("-" * 100)
    for r in results:
        v1_cell = (
            f"OK {r.v1_hazard_count}h {r.v1_elapsed_s:.0f}s reg={r.v1_reg_coverage:.0%}"
            if r.v1_ok
            else f"FAIL"
        )
        v2_cell = (
            f"OK {r.v2_finding_count}f/{r.v2_uncertain_count}u {r.v2_elapsed_s:.0f}s reg={r.v2_reg_coverage:.0%}"
            if r.v2_ok
            else f"FAIL"
        )
        print(f"{r.case[:55]:<55} {v1_cell:<22} {v2_cell:<22}")
    print("-" * 100)
    v1_ok = sum(1 for r in results if r.v1_ok)
    v2_ok = sum(1 for r in results if r.v2_ok)
    v1_total_hz = sum(r.v1_hazard_count for r in results if r.v1_ok)
    v2_total_f = sum(r.v2_finding_count for r in results if r.v2_ok)
    v2_total_cost = sum(r.v2_cost_usd for r in results if r.v2_ok)
    print(
        f"v1: parse_ok={v1_ok}/{len(results)}  total_hazards={v1_total_hz}"
    )
    print(
        f"v2: parse_ok={v2_ok}/{len(results)}  total_findings={v2_total_f}  "
        f"cost=${v2_total_cost:.4f}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only", help="only run a specific case (e.g. case_001 or 1)", default=None
    )
    parser.add_argument("--skip-v1", action="store_true")
    parser.add_argument("--skip-v2", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)

    images = sorted(FIXTURES_IMG.glob("case_*.jpg"))
    if args.only:
        target = args.only.lower().replace("case_", "").lstrip("0") or "1"
        images = [p for p in images if str(int(p.name.split("_", 2)[1])) == target]
        if not images:
            raise SystemExit(f"no match for --only {args.only!r}")

    settings = Settings(safety_skills_root=SKILLS_ROOT)
    loader = SkillLoader(SKILLS_ROOT)

    results: list[CaseResult] = []
    for img in images:
        r = await run_case(img, settings, loader, args.skip_v1, args.skip_v2)
        results.append(r)
        # 增量落 summary，怕跑到一半挂断
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "_summary.json").write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
