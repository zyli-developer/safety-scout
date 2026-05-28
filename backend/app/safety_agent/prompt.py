"""PromptBuilder —— 把 SkillLoader 的内容拼成 v2 Agent 的 system prompt。

设计要点：
- 全部 L2 场景清单一次性 inline 进 system prompt（当前 12 个场景 × ~1.5k tokens = 17k）。
  之前用 `load_scenario_skill` 工具按需加载是为"防 prompt 膨胀"，但实测延迟代价
  （4 个串行 tool turn + 1 个 ToolSearch 探索）远大于多 17k cached input 的收益。
  Anthropic prompt caching 把后续 cache_read 价压到 0.1×，inline 几乎免费。
- 通过 `submit_safety_report` 工具提交报告（structured output 切换由后续 commit 做）。
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
        """每次分析的第一条 user 消息 —— 图片单独以 image block 附带。"""
        extra_block = f"\n附加信息：{extra_context}\n" if extra_context else ""
        return (
            "请按以下流程对附带的工地照片进行安全隐患分析：\n\n"
            "1. 先描述整张图片的整体场景和九宫格分区内容\n"
            "2. 判断命中的场景（参考 system prompt 的「L2 场景详细清单」）\n"
            "3. 对照 L1 + 命中场景的 L2 清单逐项核查（清单已全部在 system prompt 里，"
            "无需调用任何工具加载）\n"
            "4. 自我审查（重点对照「致命 7 类」）\n"
            "5. **必须通过调用 submit_safety_report 工具提交最终 JSON 报告**\n"
            "   不要在普通消息里输出 JSON 文本。"
            f"{extra_block}\n"
            "开始分析。"
        )
