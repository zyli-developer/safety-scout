"""judge_rubric 单测 —— 锁住关键约束（doc §4.2）。

防回归：rubric 是 Layer 2 的核心 prompt 契约，任何措辞改动必须 bump
JUDGE_RUBRIC_VERSION 否则破坏历史 verdict 可比性。
"""

from __future__ import annotations

from app.quality.judge_rubric import (
    JUDGE_RUBRIC,
    JUDGE_RUBRIC_VERSION,
    render_judge_prompt,
)


def test_version_is_string_and_non_empty() -> None:
    assert isinstance(JUDGE_RUBRIC_VERSION, str)
    assert JUDGE_RUBRIC_VERSION


def test_rubric_enforces_blind_evaluation() -> None:
    """盲评是 self-preference 防御的核心 —— rubric 必须显式禁止推测版本。"""
    assert "不知道" in JUDGE_RUBRIC
    assert "别推测" in JUDGE_RUBRIC


def test_rubric_enforces_four_dimensions() -> None:
    """4 个维度 + overall 是 schema 不可变契约。"""
    for dim in ("recall", "precision", "regulation_quality", "action_actionability"):
        assert dim in JUDGE_RUBRIC, f"rubric 缺维度: {dim}"


def test_rubric_enforces_json_only_output() -> None:
    """judge 必须返 JSON，否则 parse_judge_response 会抛错。"""
    assert "只" in JUDGE_RUBRIC and "JSON" in JUDGE_RUBRIC


def test_rubric_warns_against_count_bias() -> None:
    """rubric 必须明确告诉 judge 不要被 finding 数量绝对值吸引。"""
    assert "多不等于好" in JUDGE_RUBRIC


def test_rubric_warns_against_fabrication_in_regulation() -> None:
    """regulation_quality 维度的核心是不编造 —— 必须显式约束。"""
    assert "编造" in JUDGE_RUBRIC


def test_render_judge_prompt_embeds_both_reports() -> None:
    a = '{"finding": "A report"}'
    b = '{"finding": "B report"}'
    prompt = render_judge_prompt(a, b)
    assert "报告 A" in prompt
    assert "报告 B" in prompt
    assert a in prompt
    assert b in prompt
    # rubric 必须在最前面（先解释规则再给数据）
    assert prompt.index("=== 报告 A ===") > prompt.index("recall")
