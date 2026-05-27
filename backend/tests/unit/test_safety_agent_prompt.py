"""PromptBuilder 单元测试。

覆盖：
- system prompt 包含所有 6 个段落
- 场景列表 12 条全部列出 + Agent 知道用哪个 tool 加载
- initial user message 强制要求调用 submit_safety_report
- 长度在合理区间（~4000-6000 tokens，约 8000-12000 字符）
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
        "# 可用场景列表",
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


def test_system_prompt_mentions_load_tool(builder: PromptBuilder) -> None:
    sp = builder.build_system_prompt()
    assert "load_scenario_skill" in sp


def test_system_prompt_length_in_range(builder: PromptBuilder) -> None:
    sp = builder.build_system_prompt()
    # 中文 2 字符 ≈ 1 token；目标 4000-7500 tokens（v2 新增重大隐患判定段后略涨），
    # 对应 ~8000-15000 字符。留一点缓冲：[5000, 20000]
    assert 5000 <= len(sp) <= 20000, f"system prompt 长度异常: {len(sp)} 字符"


def test_initial_user_message_forces_submit_tool(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message()
    assert "submit_safety_report" in msg
    assert "load_scenario_skill" in msg


def test_initial_user_message_with_extra_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message(extra_context="在建主体 5 楼，上海")
    assert "在建主体 5 楼，上海" in msg


def test_initial_user_message_no_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message()
    assert "附加信息" not in msg
