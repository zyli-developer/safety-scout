"""PromptBuilder —— 把 SkillLoader 的内容拼成 v2 Agent 的 system prompt。

设计要点（v4 两阶段架构）：
- Stage 1 **场景识别**：极简 prompt（role + 场景目录 meta，不含任何 L2 详情，
  约 5-8k tokens），让模型快速判图属于哪些场景，通过 submit_scene_detection
  工具回传命中 ID 列表。
- Stage 2 **深度分析**：根据 stage 1 命中的场景动态拼 system prompt，只 inline
  那 3-5 个场景的 L2 清单（约 8-12k tokens），减少模型对照清单的认知负担和
  首 token 处理时间。
- 兜底：如果 stage 1 失败 / 返回空列表，stage 2 退回到全 12 inline（即 v3 旧
  单阶段行为）。

历史：
- v3 单阶段：12 场景全 inline（22k system prompt），实测 ~115s（Opus）。
- v2 短暂的 structured output：CLI 虚拟工具，Sonnet 不会用，已弃。
- v3 → v4 切两阶段是为了降低 stage 2 上下文，看模型能不能"想得更快"。
- 通过自定义 MCP 工具提交最终 JSON（stage 1: submit_scene_detection，
  stage 2: submit_safety_report），CoT 推理走 extended thinking 内部通道。
"""
from __future__ import annotations

from app.safety_agent.loader import SkillLoader


class PromptBuilder:
    """工地安全分析提示词组装器。"""

    SEPARATOR = "\n\n" + "=" * 60 + "\n\n"

    def __init__(self, skill_loader: SkillLoader) -> None:
        self.loader = skill_loader

    # ---------- v3 单阶段（兜底） / v4 stage 2 复用 ----------

    def build_system_prompt(self, scene_ids: list[str] | None = None) -> str:
        """v4 stage 2 / v3 兜底用的 system prompt。

        Args:
            scene_ids: None = 全部 12 个场景 inline（v3 行为 / stage 1 失败兜底）；
                       list[str] = 只 inline 命中的子集（v4 stage 2 正常路径）。

        组成：role / 分析流程 / L1 / 致命 / 重大判定 / 输出规范 / L2 命中场景
        """
        scenarios_inline = self.loader.get_scenarios_inline(scene_ids)
        if scene_ids is None:
            l2_title = "# L2 场景详细清单（全部 12 个，按命中情况对照核查）"
        else:
            ids_str = "、".join(scene_ids) if scene_ids else "无"
            l2_title = f"# L2 命中场景详细清单（stage 1 已识别：{ids_str}）"

        sections: list[tuple[str, str]] = [
            ("# 角色定义", self.loader.get_shared("role_definition")),
            ("# 分析流程", self.loader.get_shared("cot_instructions")),
            ("# L1 必查清单（每张图必查）", self.loader.get_l1_checklist()),
            ("# 致命隐患强化", self.loader.get_shared("fatal_warnings")),
            (
                "# 重大事故隐患判定（建质规〔2024〕5号）",
                self.loader.get_shared("major_hazard_judgment"),
            ),
            ("# 输出格式规范", self.loader.get_shared("output_schema")),
            (l2_title, scenarios_inline),
        ]
        return self.SEPARATOR.join(f"{title}\n\n{body}" for title, body in sections)

    def build_initial_user_message(
        self,
        extra_context: str = "",
        scene_ids: list[str] | None = None,
    ) -> str:
        """Stage 2 / 单阶段 user 消息。

        scene_ids 来自 stage 1；如果传了，提示词里告诉模型"识别已完成"避免
        重复识别浪费 token。
        """
        extra_block = f"\n附加信息：{extra_context}\n" if extra_context else ""
        if scene_ids:
            scene_block = (
                f"\n命中场景已由 Stage 1 识别为：{', '.join(scene_ids)}。"
                "system prompt 里只 inline 了这些场景的 L2 清单 + L1 必查 + 致命强化，"
                "请直接对照核查、不要再做场景识别。\n"
            )
        else:
            scene_block = ""
        return (
            "请对附带的工地照片做安全隐患分析。先用 Read 工具读取图片，然后按 system "
            "prompt 中的「分析流程」逐项核查（L1 必查 + 命中场景的 L2 清单，均已 inline）。"
            f"{scene_block}"
            f"{extra_block}\n"
            "**输出约束（严格遵守）**：\n"
            "- **必须通过调用 `submit_safety_report` 工具提交最终 JSON 报告**，"
            "不要在普通消息里输出 JSON 文本\n"
            "- submit 之前/之后不要输出过程性解释、思路、分析步骤；CoT 推理走 extended "
            "thinking 内部通道，不要在最终回复里复述\n"
            "- `findings`：存在隐患的项全部列出，描述要可操作、不要赘述\n"
            "- `no_findings` **最多 5 条**：只挑现场最容易被外行质疑漏检的项（如安全帽、"
            "防护栏的常见高发项），其余不必列；每条只写 check_id + 极简 note\n"
            "- `uncertain` **最多 3 条**：只列真正会影响整改判断、必须人工现场复核的项；"
            "细枝末节的不确定不要写"
        )

    # ---------- v4 stage 1：场景识别 ----------

    def build_stage1_system_prompt(self) -> str:
        """v4 stage 1：只含 role + 场景目录 meta（不含 L2），约 5-8k tokens。

        目标：模型 5-15s 内识别图属于哪几个场景类别，调 submit_scene_detection
        提交命中 ID 列表，然后结束。
        """
        sections: list[tuple[str, str]] = [
            ("# 角色定义", self.loader.get_shared("role_definition")),
            ("# 当前任务", self._stage1_task_doc()),
            ("# 场景目录（按需识别命中项）", self._build_scenario_meta_list()),
        ]
        return self.SEPARATOR.join(f"{title}\n\n{body}" for title, body in sections)

    def build_stage1_user_message(self, extra_context: str = "") -> str:
        """v4 stage 1 user message：要求 Read 图、识别场景、调 submit_scene_detection。"""
        extra_block = f"\n附加信息：{extra_context}\n" if extra_context else ""
        return (
            "请对附带的工地照片做**场景识别**（不做深度安全分析）。"
            "先用 Read 工具读取图片，然后判断这张图属于"
            "system prompt 中「场景目录」列出的哪几个场景。"
            f"{extra_block}\n"
            "**约束**：\n"
            "- **必须通过调用 `submit_scene_detection` 工具提交命中场景 ID 列表**，"
            "如 ['S03', 'S05']。不要在普通消息里输出 ID 列表\n"
            "- 宁可宽松命中也不要漏（漏掉的场景在 stage 2 拿不到 L2 清单，会导致深度漏检）；"
            "建议命中 2-5 个最相关场景\n"
            "- 不要输出场景描述/分析过程/解释；只调工具，不要其它\n"
            "- 提交后立刻结束，无需进一步分析（深度分析由 stage 2 接手）"
        )

    def _stage1_task_doc(self) -> str:
        return (
            "**这是两阶段分析的 Stage 1：场景识别**\n\n"
            "你的唯一职责：看图后判断这张工地照片属于「场景目录」中的哪些场景类别，"
            "通过工具 `submit_scene_detection` 提交命中场景 ID 列表（list[str]）。\n\n"
            "Stage 2 会拿到你提交的命中场景，加载对应的 L2 详细清单（每场景 30-80 个具体"
            "检查项）做深度安全分析。你**不要**做任何检查项核查、不要列隐患，那是 stage 2 的事。"
        )

    def _build_scenario_meta_list(self) -> str:
        """场景目录 markdown：ID + 中文名 + trigger_features 摘要。

        给 stage 1 用 —— 模型靠这个判图属于哪个场景，不需要 L2 详情。
        """
        lines = ["| ID | 场景 | 典型视觉特征 |", "|----|------|---------------|"]
        for s in self.loader.list_scenarios():
            features = "、".join(s["trigger_features"][:5])
            lines.append(f"| {s['id']} | {s['name']} | {features} |")
        return "\n".join(lines)
