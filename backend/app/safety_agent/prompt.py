"""PromptBuilder —— 把 SkillLoader 的内容拼成 v2 Agent 的 system prompt。

设计要点：
- 只组装"每次都需要"的部分（角色 / CoT / L1 / 致命强化 / 输出 schema / 场景目录）；
  L2 详细清单走 tool `load_scenario_skill` 按命中场景按需注入，避免 system prompt 膨胀。
- 强制约束 Agent 必须通过 `submit_safety_report` tool 提交报告（不要让它自由打印 JSON）；
  initial user message 里再次强调这一点。
- SEPARATOR 用 60 个 `=` 帮 Agent 视觉切分段落，prompt 长度估算 ~4000-6000 tokens。
"""
from __future__ import annotations

from app.safety_agent.loader import SkillLoader


class PromptBuilder:
    """工地安全分析提示词组装器。"""

    SEPARATOR = "\n\n" + "=" * 60 + "\n\n"

    def __init__(self, skill_loader: SkillLoader) -> None:
        self.loader = skill_loader

    def build_system_prompt(self) -> str:
        """启动时的 system prompt（不含 L2 详细清单）。"""
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
            ("# 可用场景列表", self._build_scenario_list()),
        ]
        return self.SEPARATOR.join(f"{title}\n\n{body}" for title, body in sections)

    def build_initial_user_message(self, extra_context: str = "") -> str:
        """每次分析的第一条 user 消息 —— 图片单独以 image block 附带。"""
        extra_block = f"\n附加信息：{extra_context}\n" if extra_context else ""
        return (
            "请按以下流程对附带的工地照片进行安全隐患分析：\n\n"
            "1. 先描述整张图片的整体场景和九宫格分区内容\n"
            "2. 判断命中的场景（参考可用场景列表）\n"
            "3. **必须调用 load_scenario_skill 工具加载命中场景的 L2 清单**\n"
            "4. 对照 L1 + L2 清单逐项核查\n"
            "5. 自我审查（重点对照「致命 7 类」）\n"
            "6. **必须通过调用 submit_safety_report 工具提交最终 JSON 报告**\n"
            "   不要在普通消息里输出 JSON 文本。"
            f"{extra_block}\n"
            "开始分析。"
        )

    def _build_scenario_list(self) -> str:
        scenarios = self.loader.list_scenarios()
        lines = [
            "你可以通过调用 `load_scenario_skill(scenario_id)` 工具加载以下场景的详细清单：",
            "",
        ]
        for s in scenarios:
            features = "、".join(s["trigger_features"][:4])
            lines.append(f"- **{s['id']}** {s['name']}（特征：{features}）")
        lines.append("")
        lines.append(
            "**重要**：在 Step 2 场景识别完成后，必须主动调用此工具加载命中场景的清单，"
            "再进入 Step 3 核查。"
        )
        return "\n".join(lines)
