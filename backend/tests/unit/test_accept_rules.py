"""accept_rules 5 条 gate 单测 —— 每条独立覆盖（doc §4.6）。

任一规则改阈值必须在 doc 和此文件同步更新。
"""

from __future__ import annotations

from app.quality.accept_rules import (
    MAX_INCONCLUSIVE_RATIO,
    MIN_WIN_MARGIN_IMAGES,
    PRECISION_TOLERANCE_PP,
    evaluate,
)


def _base_kwargs(**overrides):
    """好场景默认值 —— 所有 gate 都过；测试时只覆盖关注的字段。"""
    d = dict(
        overall_counts={"baseline": 1, "candidate": 6, "tie": 1},  # margin = 5
        recall_counts={"baseline": 1, "candidate": 7, "tie": 0},
        precision_counts={"baseline": 3, "candidate": 4, "tie": 1},
        inconclusive=1,  # 1/9 ≈ 11%
        confident=8,
        baseline_p50_latency_ms=200000.0,
        candidate_p50_latency_ms=150000.0,
    )
    d.update(overrides)
    return d


def test_all_gates_pass_returns_accept() -> None:
    rep = evaluate(**_base_kwargs())
    assert rep.verdict == "ACCEPT"
    assert all(g.passed for g in rep.gates)


# === Gate 1: overall_margin ===


def test_overall_margin_below_threshold_rejects() -> None:
    rep = evaluate(**_base_kwargs(
        overall_counts={"baseline": 2, "candidate": 4, "tie": 0}  # margin = 2 < 3
    ))
    assert rep.verdict == "REJECT"
    g = next(g for g in rep.gates if g.name == "overall_margin")
    assert not g.passed
    assert str(MIN_WIN_MARGIN_IMAGES) in g.detail


def test_overall_margin_exactly_at_threshold_passes() -> None:
    rep = evaluate(**_base_kwargs(
        overall_counts={"baseline": 1, "candidate": 4, "tie": 0}  # margin = 3
    ))
    g = next(g for g in rep.gates if g.name == "overall_margin")
    assert g.passed


# === Gate 2: recall_no_regression ===


def test_recall_regression_rejects() -> None:
    rep = evaluate(**_base_kwargs(
        recall_counts={"baseline": 5, "candidate": 3, "tie": 0}  # baseline > candidate
    ))
    g = next(g for g in rep.gates if g.name == "recall_no_regression")
    assert not g.passed
    assert rep.verdict == "REJECT"


def test_recall_equal_passes() -> None:
    rep = evaluate(**_base_kwargs(
        recall_counts={"baseline": 4, "candidate": 4, "tie": 0}
    ))
    g = next(g for g in rep.gates if g.name == "recall_no_regression")
    assert g.passed


# === Gate 3: precision_tolerance ===


def test_precision_within_tolerance_passes() -> None:
    """confident=10, baseline win 5(50%), candidate win 4(40%) → 退化 10pp ≤ 15pp。"""
    rep = evaluate(**_base_kwargs(
        precision_counts={"baseline": 5, "candidate": 4, "tie": 1},
        confident=10,
    ))
    g = next(g for g in rep.gates if g.name == "precision_tolerance")
    assert g.passed


def test_precision_exceeds_tolerance_rejects() -> None:
    """confident=10, baseline win 8(80%), candidate win 1(10%) → 退化 70pp > 15pp。"""
    rep = evaluate(**_base_kwargs(
        precision_counts={"baseline": 8, "candidate": 1, "tie": 1},
        confident=10,
    ))
    g = next(g for g in rep.gates if g.name == "precision_tolerance")
    assert not g.passed
    assert rep.verdict == "REJECT"


def test_precision_no_confident_fails_gate() -> None:
    """没有 confident verdict 时无法统计 precision —— gate 失败（保守起见）。"""
    rep = evaluate(**_base_kwargs(confident=0, precision_counts={"baseline": 0, "candidate": 0, "tie": 0}))
    g = next(g for g in rep.gates if g.name == "precision_tolerance")
    assert not g.passed


# === Gate 4: inconclusive_ratio ===


def test_inconclusive_within_limit_passes() -> None:
    """30% 内 OK。"""
    rep = evaluate(**_base_kwargs(inconclusive=2, confident=8))  # 2/10 = 20%
    g = next(g for g in rep.gates if g.name == "inconclusive_ratio")
    assert g.passed


def test_inconclusive_over_limit_rejects() -> None:
    """5/10 = 50% > 30% → REJECT。"""
    rep = evaluate(**_base_kwargs(inconclusive=5, confident=5))
    g = next(g for g in rep.gates if g.name == "inconclusive_ratio")
    assert not g.passed
    assert f"{MAX_INCONCLUSIVE_RATIO*100:.0f}%" in g.detail


def test_zero_total_passes_inconclusive_gate() -> None:
    """无数据时 inconclusive=0/0 算 0% 通过（其他 gate 会挂）。"""
    rep = evaluate(**_base_kwargs(inconclusive=0, confident=0,
                                   overall_counts={"baseline":0,"candidate":0,"tie":0}))
    g = next(g for g in rep.gates if g.name == "inconclusive_ratio")
    assert g.passed  # 0/0 = 0% ≤ 30%


# === Gate 5: latency_no_regression ===


def test_latency_improved_passes() -> None:
    rep = evaluate(**_base_kwargs(
        baseline_p50_latency_ms=200000,
        candidate_p50_latency_ms=150000,  # candidate 更快 → pass
    ))
    g = next(g for g in rep.gates if g.name == "latency_no_regression")
    assert g.passed
    assert "0.75x" in g.detail


def test_latency_regressed_rejects() -> None:
    rep = evaluate(**_base_kwargs(
        baseline_p50_latency_ms=100000,
        candidate_p50_latency_ms=120000,  # candidate 慢 20% → fail
    ))
    g = next(g for g in rep.gates if g.name == "latency_no_regression")
    assert not g.passed
    assert rep.verdict == "REJECT"


def test_latency_missing_data_skipped_as_pass() -> None:
    """没数据不算失败 —— gate 跳过（doc §4.6）。"""
    rep = evaluate(**_base_kwargs(
        baseline_p50_latency_ms=None,
        candidate_p50_latency_ms=None,
    ))
    g = next(g for g in rep.gates if g.name == "latency_no_regression")
    assert g.passed
    assert "跳过" in g.detail


def test_latency_strict_ratio_for_perf_pr() -> None:
    """性能 PR 可以传更严格的 ratio（如 0.7 表示必须 -30%）。"""
    rep = evaluate(**_base_kwargs(
        baseline_p50_latency_ms=200000,
        candidate_p50_latency_ms=180000,  # 只 -10%
        latency_gate_ratio=0.7,           # 要求 -30%
    ))
    g = next(g for g in rep.gates if g.name == "latency_no_regression")
    assert not g.passed


# === failed_gates 辅助 ===


def test_failed_gates_lists_only_failures() -> None:
    rep = evaluate(**_base_kwargs(
        overall_counts={"baseline": 5, "candidate": 1, "tie": 0},  # margin = -4
        recall_counts={"baseline": 5, "candidate": 1, "tie": 0},  # 退化
    ))
    failed = rep.failed_gates()
    failed_names = {g.name for g in failed}
    assert "overall_margin" in failed_names
    assert "recall_no_regression" in failed_names
    # latency / precision / inconclusive 还是 pass
    assert "latency_no_regression" not in failed_names
