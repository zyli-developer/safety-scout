"""
Prompt 组装器
将各 skill 模块按规则拼装为最终 system prompt。
"""

from skill_loader import SkillLoader


class PromptBuilder:
    """工地安全分析提示词组装器"""

    SEPARATOR = "\n\n" + "=" * 60 + "\n\n"

    def __init__(self, skill_loader: SkillLoader):
        self.loader = skill_loader

    def build_system_prompt(self) -> str:
        """
        构建启动时的 system prompt（不包含场景 L2 清单）
        场景 L2 由 Agent 通过 tool 按需加载，加载后由 Agent 持有在 context 中
        """
        sections = [
            ("# 角色定义", self.loader.get_shared("role_definition")),
            ("# 分析流程", self.loader.get_shared("cot_instructions")),
            ("# L1 必查清单（每张图必查）", self.loader.get_l1_checklist()),
            ("# 致命隐患强化", self.loader.get_shared("fatal_warnings")),
            ("# 输出格式规范", self.loader.get_shared("output_schema")),
            ("# 可用场景列表", self._build_scenario_list()),
        ]

        return self.SEPARATOR.join(
            f"{title}\n\n{content}" for title, content in sections
        )

    def _build_scenario_list(self) -> str:
        """构建场景列表说明（让 Agent 知道哪些 L2 可调用）"""
        scenarios = self.loader.list_scenarios()
        lines = [
            "你可以通过调用 `load_scenario_skill(scenario_id)` 工具加载以下场景的详细清单：",
            ""
        ]
        for s in scenarios:
            features = "、".join(s["trigger_features"][:4])
            lines.append(f"- **{s['id']}** {s['name']}（特征：{features}）")
        lines.append("")
        lines.append("**重要**：在 Step 2 场景识别完成后，必须主动调用此工具加载命中场景的清单，再进入 Step 3 核查。")
        return "\n".join(lines)

    def build_initial_user_message(self, image_description: str = "") -> str:
        """
        构建第一条 user message
        """
        return f"""请按以下流程对附加的工地照片进行安全隐患分析：

1. 先描述整张图片的整体场景和九宫格分区内容
2. 判断命中的场景（参考可用场景列表）
3. **必须调用 load_scenario_skill 工具加载命中场景的 L2 清单**
4. 对照 L1 + L2 清单逐项核查
5. 自我审查（重点对照"致命 7 类"）
6. 输出最终 JSON 报告

{f"附加信息：{image_description}" if image_description else ""}

开始分析。"""


# 使用示例
if __name__ == "__main__":
    loader = SkillLoader("/path/to/safety_skills")
    builder = PromptBuilder(loader)
    
    system_prompt = builder.build_system_prompt()
    print(f"System prompt 字符数: {len(system_prompt)}")
    print(f"估算 token: {len(system_prompt) // 2}")  # 中文大约 2 字符 1 token
