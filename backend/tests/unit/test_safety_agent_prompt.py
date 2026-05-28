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


# ---------- v4 两阶段：stage 1 prompt ----------


def test_stage1_system_prompt_has_meta_no_l2(builder: PromptBuilder) -> None:
    """Stage 1 prompt 只含场景目录 meta（ID + 名 + 特征），不含任何 L2 详情。

    L2 详情应留给 stage 2 按命中场景动态注入。这里硬断言 stage 1 长度
    显著小于 stage 2 全 inline。
    """
    sp1 = builder.build_stage1_system_prompt()
    sp2_full = builder.build_system_prompt()  # 全 inline 22-36k
    assert "S03" in sp1  # 场景目录里 ID 必须出现
    assert "S12" in sp1
    # 应远小于全 inline；上限 18k 字符，下限象征性给 500
    # （实测目前 ~1.5k 字符 = 中文 ~750 tokens，stage 1 任务简单不需要更长）
    assert 500 <= len(sp1) <= 18000, f"stage1 prompt 异常长度: {len(sp1)}"
    assert len(sp1) < len(sp2_full) / 2, (
        f"stage1 ({len(sp1)}) 应远小于 stage2 全 inline ({len(sp2_full)})"
    )


def test_stage1_system_prompt_mentions_detection_tool(builder: PromptBuilder) -> None:
    """Stage 1 prompt 必须明示工具名 submit_scene_detection。"""
    sp1 = builder.build_stage1_system_prompt()
    assert "submit_scene_detection" in sp1 or "stage 1" in sp1.lower() or "场景识别" in sp1


def test_stage1_user_message_requires_detection_tool(builder: PromptBuilder) -> None:
    msg = builder.build_stage1_user_message()
    assert "submit_scene_detection" in msg
    # stage 1 不应让模型做深度分析
    assert "submit_safety_report" not in msg


def test_stage1_scenario_meta_lists_all_12(builder: PromptBuilder) -> None:
    """场景目录 meta 必须列全 12 个，否则 stage 1 漏掉的场景永远进不去 stage 2。"""
    sp1 = builder.build_stage1_system_prompt()
    for sid in ("S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"):
        assert sid in sp1, f"stage1 prompt 漏场景 {sid}"


# ---------- v4 两阶段：stage 2 subset prompt ----------


def test_build_system_prompt_with_scene_subset(builder: PromptBuilder) -> None:
    """build_system_prompt(scene_ids=[...]) 只 inline 指定场景的 L2。"""
    full = builder.build_system_prompt()  # 全 12 inline
    subset = builder.build_system_prompt(scene_ids=["S03", "S05"])
    assert len(subset) < len(full), "子集 prompt 必须比全 inline 短"
    assert "S03" in subset
    assert "S05" in subset
    # 命中的子集 prompt 大小应是全集的一小部分（场景占大头）
    assert len(subset) < len(full) * 0.7


def test_build_system_prompt_with_empty_subset_falls_back_to_all(
    builder: PromptBuilder,
) -> None:
    """scene_ids=None 或 [] → 走全 inline 兜底（等价旧 v3 行为）。"""
    full = builder.build_system_prompt()
    none_arg = builder.build_system_prompt(scene_ids=None)
    assert full == none_arg


def test_initial_user_message_with_scene_ids_mentions_them(
    builder: PromptBuilder,
) -> None:
    """传 scene_ids 给 user message 时，必须告诉模型"识别已完成"避免重复。"""
    msg = builder.build_initial_user_message(scene_ids=["S03", "S05"])
    assert "S03" in msg
    assert "S05" in msg
    # 必须明示"已识别 / Stage 1" 避免模型重复识别
    assert any(kw in msg for kw in ["已识别", "Stage 1", "stage 1", "stage1"])


def test_initial_user_message_uses_submit_tool_not_legacy_load(
    builder: PromptBuilder,
) -> None:
    """提示词必须引导模型用 submit_safety_report 提交报告，且 load_scenario_skill
    已下线不应再被提及（场景已 inline 进 system prompt）。

    历史：曾短暂改为 native structured output（drop submit 工具），但 Sonnet 4.6
    不会用 CLI 虚拟工具 StructuredOutput，已回退到 submit 工具路径。
    """
    msg = builder.build_initial_user_message()
    assert "submit_safety_report" in msg
    assert "load_scenario_skill" not in msg


def test_initial_user_message_enforces_pure_json_output(builder: PromptBuilder) -> None:
    """禁过程文本约束：必须告诉模型"最终只回 JSON，不要解释/思路/markdown 围栏"。
    缺这条约束会让模型回退到"边想边说"，输出 token 暴涨。
    """
    msg = builder.build_initial_user_message()
    assert "JSON" in msg
    # 至少有一条针对"不要输出过程文本"的明示约束
    assert any(kw in msg for kw in ["不要", "仅为", "严格"])


def test_initial_user_message_caps_no_findings_and_uncertain(builder: PromptBuilder) -> None:
    """新增性能约束：prompt 必须明示 no_findings ≤ 5 / uncertain ≤ 3。"""
    msg = builder.build_initial_user_message()
    assert "no_findings" in msg
    assert "5" in msg
    assert "uncertain" in msg
    assert "3" in msg


def test_initial_user_message_enforces_field_budgets(builder: PromptBuilder) -> None:
    """v4.1：user message 必须明示字段字数 budget（description ≤25、regulation
    ≤15、action ≤40）。这是 output_tokens 压缩的关键约束 —— 单靠 schema 例子
    建议不够，user message 再强化一次。"""
    msg = builder.build_initial_user_message()
    # 至少出现这几个关键字段名和数字
    assert "description" in msg
    assert "regulation" in msg
    assert "25" in msg  # description budget
    assert "15" in msg  # regulation budget
    assert "40" in msg  # action budget


def test_initial_user_message_caps_key_recommendations(builder: PromptBuilder) -> None:
    """summary.key_recommendations 也要 cap（之前 3 条 × 20 tok = 60 tok，
    cap 到 2 条）—— prompt 应提到。"""
    msg = builder.build_initial_user_message()
    assert "key_recommendations" in msg
    assert "2" in msg  # 最多 2 条


def test_initial_user_message_no_field_overlap_instruction(
    builder: PromptBuilder,
) -> None:
    """description / action / regulation 三个字段必须独立 —— prompt 显式禁止
    互相复述（实测模型常在 description 里把 regulation 文字也铺一遍）。"""
    msg = builder.build_initial_user_message()
    # 包含某种"独立 / 不复述 / 不重复"的指令
    assert any(kw in msg for kw in ["独立", "不复述", "不要互相", "不要复述", "不与"])


def test_initial_user_message_with_extra_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message(extra_context="在建主体 5 楼，上海")
    assert "在建主体 5 楼，上海" in msg


def test_initial_user_message_no_context(builder: PromptBuilder) -> None:
    msg = builder.build_initial_user_message()
    assert "附加信息" not in msg
