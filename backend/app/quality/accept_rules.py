"""判定接受规则（docs/specs/quality-tracking.md §4.6）。

5 条 gate，candidate 必须**全部通过**才返回 ACCEPT，否则 REJECT。

写成纯函数 + dataclass，方便单测覆盖每条规则；CLI 拿 `evaluate()` 直接 print。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["ACCEPT", "REJECT"]


@dataclass(frozen=True)
class GateResult:
    """单条 gate 的判定结果。"""

    name: str
    passed: bool
    detail: str  # 给用户看的一句话解释


@dataclass(frozen=True)
class AcceptanceReport:
    """完整接受判定 —— 5 条 gate + 最终 verdict。"""

    verdict: Verdict
    gates: list[GateResult]

    def failed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]


# 接受门阈值（doc §4.6）——
# 改动这些数值必须在 doc 和测试中同步更新。
MIN_WIN_MARGIN_IMAGES = 3       # candidate_wins - baseline_wins ≥ 3 张图
MAX_INCONCLUSIVE_RATIO = 0.30   # inconclusive 占比 ≤ 30%
PRECISION_TOLERANCE_PP = 0.15   # precision 退化容忍 15pp
LATENCY_IMPROVE_RATIO = 1.0     # candidate.p50_latency ≤ baseline.p50_latency
# 性能 gate 默认要求"不退化"；如果是性能优化 PR，外部传 LATENCY_OPTIMIZE_RATIO 严格化


def evaluate(
    *,
    overall_counts: dict[str, int],      # {"baseline": N, "candidate": N, "tie": N}
    recall_counts: dict[str, int],
    precision_counts: dict[str, int],
    inconclusive: int,
    confident: int,
    baseline_p50_latency_ms: float | None = None,
    candidate_p50_latency_ms: float | None = None,
    latency_gate_ratio: float = LATENCY_IMPROVE_RATIO,
) -> AcceptanceReport:
    """跑 5 条 gate，返回 AcceptanceReport。

    Args:
        overall_counts: 总体 winner 计数（confident=1 的统计）
        recall_counts / precision_counts: 维度 winner 计数
        inconclusive / confident: 位置去偏后的可信 / 不可信判定数
        baseline_p50_latency_ms / candidate_p50_latency_ms: 性能 gate 输入；
            任一 None 跳过该 gate（无数据不算失败）
        latency_gate_ratio: candidate / baseline 必须 ≤ 此比值；默认 1.0（不退化）
    """
    total = confident + inconclusive
    gates: list[GateResult] = []

    # Gate 1: Overall winner margin ≥ 3 张
    margin = overall_counts.get("candidate", 0) - overall_counts.get("baseline", 0)
    gates.append(
        GateResult(
            name="overall_margin",
            passed=margin >= MIN_WIN_MARGIN_IMAGES,
            detail=(
                f"candidate wins - baseline wins = {margin} "
                f"(需 ≥ {MIN_WIN_MARGIN_IMAGES})"
            ),
        )
    )

    # Gate 2: Recall —— candidate 不能输（要求 candidate ≥ baseline）
    recall_pass = (
        recall_counts.get("candidate", 0) >= recall_counts.get("baseline", 0)
    )
    gates.append(
        GateResult(
            name="recall_no_regression",
            passed=recall_pass,
            detail=(
                f"recall winner: candidate={recall_counts.get('candidate', 0)} "
                f"vs baseline={recall_counts.get('baseline', 0)}"
            ),
        )
    )

    # Gate 3: Precision —— candidate 退化容忍 15pp
    if confident > 0:
        cand_p = precision_counts.get("candidate", 0) / confident
        base_p = precision_counts.get("baseline", 0) / confident
        precision_regression = base_p - cand_p
        precision_pass = precision_regression <= PRECISION_TOLERANCE_PP
        gates.append(
            GateResult(
                name="precision_tolerance",
                passed=precision_pass,
                detail=(
                    f"precision 退化 {precision_regression*100:.1f}pp "
                    f"(容忍 {PRECISION_TOLERANCE_PP*100:.0f}pp)"
                ),
            )
        )
    else:
        gates.append(
            GateResult(
                name="precision_tolerance",
                passed=False,
                detail="无 confident verdict 可统计 precision",
            )
        )

    # Gate 4: Inconclusive 占比
    inc_ratio = (inconclusive / total) if total > 0 else 0.0
    gates.append(
        GateResult(
            name="inconclusive_ratio",
            passed=inc_ratio <= MAX_INCONCLUSIVE_RATIO,
            detail=(
                f"inconclusive {inconclusive}/{total} = {inc_ratio*100:.1f}% "
                f"(上限 {MAX_INCONCLUSIVE_RATIO*100:.0f}%)"
            ),
        )
    )

    # Gate 5: Latency —— 不退化（性能 PR 可外部 strict 化）
    if (
        baseline_p50_latency_ms is not None
        and candidate_p50_latency_ms is not None
        and baseline_p50_latency_ms > 0
    ):
        ratio = candidate_p50_latency_ms / baseline_p50_latency_ms
        gates.append(
            GateResult(
                name="latency_no_regression",
                passed=ratio <= latency_gate_ratio,
                detail=(
                    f"candidate p50 = {candidate_p50_latency_ms:.0f}ms / "
                    f"baseline p50 = {baseline_p50_latency_ms:.0f}ms = {ratio:.2f}x "
                    f"(上限 {latency_gate_ratio:.2f}x)"
                ),
            )
        )
    else:
        gates.append(
            GateResult(
                name="latency_no_regression",
                passed=True,
                detail="无 latency 数据（gate 跳过）",
            )
        )

    verdict: Verdict = "ACCEPT" if all(g.passed for g in gates) else "REJECT"
    return AcceptanceReport(verdict=verdict, gates=gates)
