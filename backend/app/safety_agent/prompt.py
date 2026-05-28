"""PromptBuilder —— 把 SkillLoader 的内容拼成 v2 Agent 的 system prompt。

设计要点：
- 全部 L2 场景清单一次性 inline 进 system prompt（当前 12 个场景 × ~1.5k tokens = 17k）。
  之前用 `load_scenario_skill` 工具按需加载是为"防 prompt 膨胀"，但实测延迟代价
  （4 个串行 tool turn + 1 个 ToolSearch 探索）远大于多 17k cached input 的收益。
  Anthropic prompt caching 把后续 cache_read 价压到 0.1×，inline 几乎免费。
- 模型通过自定义 MCP 工具 `submit_safety_report` 提交最终 JSON 报告
  （曾短暂改为 native structured output 但 Sonnet 4.6 不会用 CLI 的虚拟工具，
  已回退；详见 agent.py 架构演进注释）。
- 强制约束 Agent 必须通过 submit_safety_report 提交，不允许在普通消息里
  自由输出 JSON。CoT 推理走 extended thinking 内部通道。
- SEPARATOR 用 60 个 `=` 帮 Agent 视觉切分段落，prompt 长度估算 ~22k tokens（含场景）。
"""
from __future__ import annotations

from app.safety_agent.loader import SkillLoader


class PromptBuilder:
    """工地安全分析提示词组装器。"""

    SEPARATOR = "\n\n" + "=" * 60 + "\n\n"

    def __init__(self, skill_loader: SkillLoader) -> None:
        self.loader = skill_loader

    def build_system_prompt(self) -> str:
        """启动时的 system prompt（含全部 12 个场景的 L2 清单 inline）。"""
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
            ("# L2 场景详细清单（全部 12 个，按命中情况对照核查）",
             self.loader.get_all_scenarios_inline()),
        ]
        return self.SEPARATOR.join(f"{title}\n\n{body}" for title, body in sections)

    def build_initial_user_message(self, extra_context: str = "") -> str:
        """每次分析的第一条 user 消息 —— 图片单独以 image block 附带。

        Native structured output 模式下，最终回复必须是一段合法的 ReportV2Payload
        JSON。本提示词配合 output_format + extended thinking：
        - 推理过程走 thinking 通道，无需也不要在最终回复里"写出来"
        - 最终回复**只输出 JSON**，不要前缀解释、不要 markdown 围栏、不要尾部寒暄
        """
        extra_block = f"\n附加信息：{extra_context}\n" if extra_context else ""
        return (
            "请对附带的工地照片做安全隐患分析。先用 Read 工具读取图片，然后按 system "
            "prompt 中的「分析流程」逐项核查（L1 必查 + 命中场景的 L2 清单，均已 inline）。"
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
