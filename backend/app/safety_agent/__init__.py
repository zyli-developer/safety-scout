"""safety_agent —— Skill 化 + Claude Agent SDK 的 v2 分析管线。

模块组成：
- loader.SkillLoader：按需读取 safety_skills/ 下的 markdown
- prompt.PromptBuilder：把 L1 + shared 模块拼成 system prompt
- tools：load_scenario_skill / submit_safety_report 两个 @tool（Phase 2 实现）
- agent.analyze_image：异步驱动 query()，从 Agent 输出中提取 v2 报告（Phase 2 实现）

v1（routes/inspections.py）走 ClaudeCLIProvider 单轮 prompt；
v2（routes/inspections_v2.py）走 Agent SDK 多轮 + tool。两者并存。
"""
from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder

__all__ = ["PromptBuilder", "SkillLoader"]
