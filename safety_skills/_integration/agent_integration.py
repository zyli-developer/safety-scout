"""
Claude Agent SDK 集成示例 - 工地安全隐患识别

依赖:
    pip install claude-agent-sdk

前置条件:
    1. 已安装 Claude Code CLI: claude --version 能正常输出
    2. 已登录 Claude 账号: claude login
    3. Claude Agent SDK 通过本地 Claude Code 调用模型，复用订阅额度，
       不需要配置 ANTHROPIC_API_KEY

注意:
    本示例的 Agent SDK API 调用方式以通用模式编写，
    具体接口以 `pip show claude-agent-sdk` 查到的版本对应的官方文档为准。
"""

import asyncio
import base64
import json
from pathlib import Path

# Claude Agent SDK 导入（具体 API 以官方文档为准）
from claude_agent_sdk import ClaudeAgentSDK, AgentOptions, tool

from skill_loader import SkillLoader
from prompt_builder import PromptBuilder


# 全局 skill 加载器（也可以注入到 Agent context）
SKILLS_ROOT = "/path/to/safety_skills"  # 修改为你的实际路径
skill_loader = SkillLoader(SKILLS_ROOT)
prompt_builder = PromptBuilder(skill_loader)


# ============================================================
# Tool 1: 加载场景清单（Agent 主动调用）
# ============================================================

@tool(
    name="load_scenario_skill",
    description=(
        "根据场景 ID 加载对应的 L2 详细检查清单。"
        "在完成场景识别（Step 2）后，必须为每个命中的场景调用此工具。"
        "返回该场景的完整检查清单 Markdown 文本。"
    )
)
async def load_scenario_skill(scenario_id: str) -> str:
    """
    加载场景 L2 清单
    
    Args:
        scenario_id: 场景编号，如 "S03", "S05", "S07"
    
    Returns:
        该场景的完整检查清单（Markdown 格式）
    """
    content = skill_loader.get_scenario(scenario_id)
    if content is None:
        available = [s["id"] for s in skill_loader.list_scenarios()]
        return f"错误：场景 ID {scenario_id} 不存在。可用场景: {available}"
    
    metadata = skill_loader.get_scenario_metadata(scenario_id)
    return f"# 已加载场景 {scenario_id} - {metadata['name']}\n\n{content}"


# ============================================================
# Tool 2: 提交最终报告（结构化输出，强制 schema）
# ============================================================

@tool(
    name="submit_safety_report",
    description=(
        "提交最终的安全隐患分析报告。"
        "report_json 必须严格符合 output_schema.md 规定的 JSON 结构。"
        "完成所有分析步骤后调用此工具结束分析。"
    )
)
async def submit_safety_report(report_json: str) -> str:
    """提交最终报告"""
    try:
        report = json.loads(report_json)
        
        # 基础校验
        required_keys = ["report_meta", "findings", "no_findings", "uncertain", "summary"]
        missing = [k for k in required_keys if k not in report]
        if missing:
            return f"报告结构不完整，缺少字段: {missing}。请补充后重新提交。"
        
        # 业务校验（可扩展）
        findings = report.get("findings", [])
        for f in findings:
            if "check_id" not in f or "severity" not in f:
                return f"findings 中存在不完整记录: {f}。请补充 check_id 和 severity。"
        
        # 保存或返回给业务层
        # TODO: 这里接入你的业务存储
        return "报告已成功接收。"
    
    except json.JSONDecodeError as e:
        return f"JSON 解析失败: {e}。请重新输出合法的 JSON。"


# ============================================================
# 主分析流程
# ============================================================

async def analyze_construction_image(
    image_path: str,
    extra_context: str = ""
) -> dict:
    """
    分析一张工地照片
    
    Args:
        image_path: 图片本地路径
        extra_context: 额外上下文信息（可选）
    
    Returns:
        分析报告 dict
    """
    # 1. 读取图片
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    image_ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if image_ext in ['jpg', 'jpeg'] else image_ext}"
    
    # 2. 构建 system prompt
    system_prompt = prompt_builder.build_system_prompt()
    initial_message = prompt_builder.build_initial_user_message(extra_context)
    
    # 3. 配置 Agent
    options = AgentOptions(
        model="claude-opus-4-7",
        system_prompt=system_prompt,
        tools=[load_scenario_skill, submit_safety_report],
        max_tool_use_iterations=15,  # 允许最多 15 次工具调用（加载场景 + 提交报告）
    )
    
    # 4. 启动 Agent，传入图片 + 引导消息
    async with ClaudeAgentSDK(options=options) as agent:
        result = await agent.run(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": initial_message},
                    ],
                }
            ]
        )
    
    # 5. 从工具调用结果中提取最终报告
    final_report = None
    for call in result.tool_calls:
        if call.name == "submit_safety_report":
            try:
                final_report = json.loads(call.input["report_json"])
            except Exception:
                pass
    
    if final_report is None:
        # Fallback: 尝试从最终 text 中解析 JSON
        text = result.final_text
        try:
            final_report = json.loads(text)
        except Exception as e:
            raise ValueError(f"无法从 Agent 输出中解析报告: {e}\n输出: {text[:500]}")
    
    return final_report


# ============================================================
# 使用示例
# ============================================================

async def main():
    image_path = "/path/to/your/construction_photo.jpg"
    
    report = await analyze_construction_image(
        image_path=image_path,
        extra_context="该照片拍摄于在建主体结构 5 楼，工地位于上海"
    )
    
    # 打印结构化报告
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    # 打印关键指标
    summary = report.get("summary", {})
    print(f"\n发现隐患: {summary.get('findings_count', 0)} 项")
    print(f"  重大: {summary.get('fatal_count', 0)}")
    print(f"  较大: {summary.get('major_count', 0)}")
    print(f"  一般: {summary.get('minor_count', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
