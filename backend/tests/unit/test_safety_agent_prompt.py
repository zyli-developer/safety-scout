"""PromptBuilder 单元测试。

覆盖：
- system prompt 包含所有段落（含 inline 后的 L2 详细清单段）
- 场景内容（12 个）全部 inline，不再要求 Agent 调用 load_scenario_skill
- initial user message 不再要求"调用 submit_safety_report"
  （native structured output 取代）；明确禁止过程性文本
- 长度在合理区间（inline 后 ~22k tokens，约 22000-50000 字符）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "safety_skills"


@pytest.fixture(scope="module")
def builder() -> PromptBuilder:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"safety_skills 未部署到 {SKILLS_ROOT}，跳过 prompt 测试")
    return PromptBuilder(SkillLoader(SKILLS_ROOT))


def test_system_prompt_has_all_sections(builder: PromptBuilder) -> None:
    sp = builder.build_system_prompt()
    for title in (
        "# 角色定义",
        "# 分析流程",
        "# L1 必查清单（每张图必查）",
        "# 致命隐患强化",
        "# 重大事故隐患判定（建质规〔2024〕5号）",
        "# 输出格式规范",
        "# L2 场景详细清单",  # inline 化后的新段标题
    ):
        assert title in sp, f"system prompt 缺段落: {title}"


def test_system_prompt_forbids_major_basis_fabrication(builder: PromptBuilder) -> None:
    """system prompt 必须明确禁止仅凭 severity 等价代换、必须保留宁缺勿造原则。"""
    sp = builder.build_system_prompt()
    assert "宁可漏判，不可误判" in sp
    assert "不允许编造条款号" in sp
    # severity=重大 ≠ is_major=true 的硬约束必须出现，避免回归到 adapter 时代的等价代换
    assert "充分条件" in sp


def test_system_prompt_lists_all_scenarios(builder: PromptBuilder) -> None:
    sp = builder.build_system_prompt()
    for sid in ("S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"):
        assert sid in sp, f"system prompt 漏场景 {sid}"


def test_system_prompt_does_not_mention_load_tool(builder: PromptBuilder) -> None:
    """回归保护：load_scenario_skill 已下线，prompt 里不应再出现这个工具名
    （否则模型会去找一个不存在的工具，触发 ToolSearch 或报错）。"""
    sp = builder.build_system_prompt()
    assert "load_scenario_skill" not in sp


def test_system_prompt_inlines_real_scenario_content(builder: PromptBuilder) -> None:
    """inline 必须把真实的 L2 内容拼进来（而不是只给个标题）—— 否则模型拿不到清单细节。"""
    sp = builder.build_system_prompt()
    # 任选一个场景：S03 落地式钢管脚手架，其 .md 文件里必然出现的特征关键词
    assert "S03" in sp
    assert "脚手架" in sp
    # L2 内容比纯元数据多，长度应远超 5k 字符（光元数据列表只占几百字符）
    assert len(sp) > 15000, f"inline 后 system prompt 仍偏短，怀疑没真正注入 L2 内容：{len(sp)}"


def test_system_prompt_length_in_range(builder: PromptBuilder) -> None:
    sp = builder.build_system_prompt()
    # inline 12 个场景后预期 ~22k tokens ≈ 22000-50000 字符（中文 2 字符 ≈ 1 token）。
    # 留缓冲：[15000, 60000]
    assert 15000 <= len(sp) <= 60000, f"system prompt 长度异常: {len(sp)} 字符"


def test_initial_user_message_drops_both_legacy_tools(builder: PromptBuilder) -> None:
    """回归保护：两个旧工具名都不应再出现在 user message。

    - load_scenario_skill：场景已 inline 进 system prompt
    - submit_safety_report：native structured output (output_format=json_schema) 取代
    """
    msg = builder.build_initial_user_message()
    assert "submit_safety_report" not in msg
    assert "load_scenario_skill" not in msg


def test_initial_user_message_enforces_pure_json_output(builder: PromptBuilder) -> None:
    """禁过程文本约束：必须告诉模型"最终只回 JSON，不要解释/思路/markdown 围栏"。
    缺这条约束会让模型回退到"边想边说"，输出 token 暴涨。
    """
    msg = builder.build_initial_user_message()
    assert "JSON" in msg
    # 至少有一条针对"不要输出过程文本"的明示约束
    assert any(kw in msg for kw in ["不要", "仅为", "严格"])


def test_initial_user_message_with_extra_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message(extra_context="在建主体 5 楼，上海")
    assert "在建主体 5 楼，上海" in msg


def test_initial_user_message_no_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message()
    assert "附加信息" not in msg
