"""judge_service 单测 —— pairwise + 位置去偏 workflow（doc §4.4）。

覆盖：
- parse_judge_response: 合法 JSON / markdown 包裹容错 / 缺字段 / 非法 enum
- judge_pair: 两次 winner 一致 → confident=True
- judge_pair: 两次 winner 矛盾 → inconclusive
- judge_pair: 解析失败 → inconclusive + 原始返回保留
- 位置归一化: A/B 翻译成 baseline/candidate 正确
"""

from __future__ import annotations

import json

import pytest

from app.quality.judge_service import (
    JudgeParseError,
    _flip_winner,
    _normalize_to_baseline_candidate,
    judge_pair,
    parse_judge_response,
)


# === 工具：构造一个最小可解析的 judge JSON 响应 ===


def _make_judge_json(overall: str = "A", confidence: str = "high") -> str:
    return json.dumps(
        {
            "by_dimension": {
                "recall": {"winner": overall, "reason": "x"},
                "precision": {"winner": overall, "reason": "x"},
                "regulation_quality": {"winner": overall, "reason": "x"},
                "action_actionability": {"winner": overall, "reason": "x"},
            },
            "overall": {"winner": overall, "summary": "x", "confidence": confidence},
        }
    )


# === parse_judge_response ===


def test_parse_valid_json() -> None:
    result = parse_judge_response(_make_judge_json("A"))
    assert result.overall_winner == "A"
    assert result.confidence == "high"
    assert result.by_dimension["recall"].winner == "A"


def test_parse_tolerates_markdown_wrapper() -> None:
    """模型偶尔会用 ```json ... ``` 包裹 —— 必须能救回。"""
    wrapped = f"```json\n{_make_judge_json('B')}\n```"
    result = parse_judge_response(wrapped)
    assert result.overall_winner == "B"


def test_parse_tolerates_leading_explanation_text() -> None:
    """模型偶尔会在 JSON 前加 '我的分析如下:'，要能容错。"""
    noisy = f"我的分析如下：\n{_make_judge_json('tie')}"
    result = parse_judge_response(noisy)
    assert result.overall_winner == "tie"


def test_parse_rejects_missing_dimension() -> None:
    bad = json.dumps(
        {
            "by_dimension": {
                "recall": {"winner": "A", "reason": "x"},
                # 缺 precision / regulation_quality / action_actionability
            },
            "overall": {"winner": "A", "summary": "x", "confidence": "high"},
        }
    )
    with pytest.raises(JudgeParseError):
        parse_judge_response(bad)


def test_parse_rejects_invalid_winner_enum() -> None:
    bad = _make_judge_json("A").replace('"winner": "A"', '"winner": "MAYBE"', 1)
    with pytest.raises(JudgeParseError):
        parse_judge_response(bad)


def test_parse_rejects_garbage() -> None:
    with pytest.raises(JudgeParseError):
        parse_judge_response("complete garbage no json")


# === 位置归一化 ===


def test_flip_winner_swaps_ab_keeps_tie() -> None:
    assert _flip_winner("A") == "B"
    assert _flip_winner("B") == "A"
    assert _flip_winner("tie") == "tie"


def test_normalize_swap_position_0() -> None:
    # swap=0: A=baseline, B=candidate
    assert _normalize_to_baseline_candidate("A", swap_position=0) == "baseline"
    assert _normalize_to_baseline_candidate("B", swap_position=0) == "candidate"
    assert _normalize_to_baseline_candidate("tie", swap_position=0) == "tie"


def test_normalize_swap_position_1() -> None:
    # swap=1: A=candidate, B=baseline
    assert _normalize_to_baseline_candidate("A", swap_position=1) == "candidate"
    assert _normalize_to_baseline_candidate("B", swap_position=1) == "baseline"
    assert _normalize_to_baseline_candidate("tie", swap_position=1) == "tie"


# === judge_pair: confident path ===


async def test_judge_pair_confident_when_swap_agrees() -> None:
    """位置 1（A=baseline）judge 选 B → candidate；位置 2（A=candidate）judge 选 A → candidate。两次都说 candidate 赢 → confident。"""
    call_count = {"n": 0}

    async def fake_judge(prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_judge_json("B")  # A=baseline, B=candidate → B(candidate) wins
        return _make_judge_json("A")  # A=candidate, B=baseline → A(candidate) wins

    verdict = await judge_pair(
        judge_call=fake_judge,
        judge_model="sonnet-test",
        baseline_report_json='{"x":1}',
        candidate_report_json='{"x":2}',
    )
    assert verdict.confident is True
    assert verdict.winner_overall == "candidate"
    assert verdict.winner_recall == "candidate"
    assert call_count["n"] == 2  # 必须跑 2 次（位置去偏）


async def test_judge_pair_inconclusive_when_swap_disagrees() -> None:
    """两次都选 A（位置敏感：第 1 次 A=baseline win，第 2 次 A=candidate win，归一化矛盾）→ inconclusive。"""

    async def fake_judge(prompt: str) -> str:
        return _make_judge_json("A")  # 每次都偏向第一个看到的

    verdict = await judge_pair(
        judge_call=fake_judge,
        judge_model="sonnet-test",
        baseline_report_json='{"x":1}',
        candidate_report_json='{"x":2}',
    )
    assert verdict.confident is False
    assert verdict.winner_overall is None
    # 原始返回必须保留（落库审计）
    assert verdict.raw_json_1 != ""
    assert verdict.raw_json_2 != ""


async def test_judge_pair_inconclusive_on_parse_failure() -> None:
    """judge 返回不可解析 JSON → inconclusive，不抛异常。"""

    async def bad_judge(prompt: str) -> str:
        return "this is not JSON at all"

    verdict = await judge_pair(
        judge_call=bad_judge,
        judge_model="sonnet-test",
        baseline_report_json='{"x":1}',
        candidate_report_json='{"x":2}',
    )
    assert verdict.confident is False
    assert verdict.raw_json_1 == "this is not JSON at all"


async def test_judge_pair_tie_both_sides_is_confident() -> None:
    """两次都 tie → confident（tie 在两个位置下意义相同）。"""

    async def tie_judge(prompt: str) -> str:
        return _make_judge_json("tie")

    verdict = await judge_pair(
        judge_call=tie_judge,
        judge_model="sonnet-test",
        baseline_report_json='{"x":1}',
        candidate_report_json='{"x":2}',
    )
    assert verdict.confident is True
    assert verdict.winner_overall == "tie"


async def test_judge_pair_carries_inspection_ids() -> None:
    """inspection_id 必须 pass through 到 verdict，便于落库 join。"""

    async def fake_judge(prompt: str) -> str:
        return _make_judge_json("tie")

    verdict = await judge_pair(
        judge_call=fake_judge,
        judge_model="x",
        baseline_report_json='{"x":1}',
        candidate_report_json='{"x":2}',
        baseline_inspection_id="abc-123",
        candidate_inspection_id="def-456",
    )
    assert verdict.baseline_inspection_id == "abc-123"
    assert verdict.candidate_inspection_id == "def-456"
