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
