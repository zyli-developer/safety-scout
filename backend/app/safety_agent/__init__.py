"""safety_agent —— Skill 化 + Claude Agent SDK 的 v2 分析管线。

模块组成：
- loader.SkillLoader：从 safety_skills/ 读 markdown，含 12 个 L2 场景的 inline 拼装
- prompt.PromptBuilder：把 L1 + shared + 全部 L2 场景拼成 system prompt
- agent.analyze_image：异步驱动 query()，native structured output 拿 v2 报告

v1（routes/inspections.py）走 ClaudeCLIProvider 单轮 prompt；
v2（routes/inspections_v2.py）走 Agent SDK + structured output + extended thinking。

历史：v2 曾用自定义 MCP 工具 load_scenario_skill / submit_safety_report，已
全部下线（场景 inline 化 + native JSON schema 取代），代码体积和延迟同步缩水。
"""
from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder

__all__ = ["PromptBuilder", "SkillLoader"]
