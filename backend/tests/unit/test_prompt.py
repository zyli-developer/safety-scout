"""Prompt 内容的最小约束测试，防止误删 / 误改。"""

from app.llm.prompt import ANALYZE_PROMPT, PROMPT_VERSION


def test_prompt_not_empty() -> None:
    assert len(ANALYZE_PROMPT) > 100


def test_prompt_enumerates_all_categories() -> None:
    """H1-H10 必须全部在 prompt 里被枚举到。"""
    for code in [f"H{i}" for i in range(1, 11)]:
        assert code in ANALYZE_PROMPT, f"prompt 缺少 {code}"


def test_prompt_enforces_json_only() -> None:
    assert "JSON" in ANALYZE_PROMPT
    assert "代码块" in ANALYZE_PROMPT or "markdown" in ANALYZE_PROMPT.lower()


def test_prompt_forbids_fabrication() -> None:
    """必须有"不允许编造"之类的约束。"""
    assert (
        "不允许" in ANALYZE_PROMPT
        or "不要编造" in ANALYZE_PROMPT
        or "留空" in ANALYZE_PROMPT
    )


def test_prompt_version_set() -> None:
    assert PROMPT_VERSION  # 非空字符串


def test_prompt_embeds_major_hazard_criteria() -> None:
    """v7 起 prompt 必须嵌入建质规〔2024〕5号 重大事故隐患判定要点。

    弱断言：只校验文号 + is_major/major_basis 字段提及 + 触发要点段标题。
    具体数值阈值（≥5m 等）不在此处断言（参 spec 注的"待 verbatim 校对"事项）。
    """
    assert "建质规〔2024〕5号" in ANALYZE_PROMPT, "prompt 必须提及判定标准文号"
    assert "is_major" in ANALYZE_PROMPT, "prompt 必须示意 is_major 字段"
    assert "major_basis" in ANALYZE_PROMPT, "prompt 必须示意 major_basis 字段"
    assert "重大事故隐患触发要点" in ANALYZE_PROMPT, "prompt 必须含触发要点段"
