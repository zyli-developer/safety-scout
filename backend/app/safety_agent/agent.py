"""v2 主分析入口 —— 用 Claude Agent SDK 驱动多轮 tool 调用。

实际 SDK 接口（pip 版 0.2.x）：
- `query(prompt, options)` → AsyncIterator[Message]
- `ClaudeAgentOptions(system_prompt, model, mcp_servers, allowed_tools, max_turns, ...)`
- 自定义工具走 `create_sdk_mcp_server` → 工具名暴露为 `mcp__<server>__<tool>`
- 图片输入沿用 v1 思路：写临时文件 + 允许 Read 工具，让 Agent 自己读

流程（与 plan §2.2 对齐）：
1. 写图片到临时文件
2. 用 PromptBuilder 拼 system prompt
3. 构造 SDK MCP server（含 load_scenario_skill / submit_safety_report）
4. allowed_tools = [Read, mcp__safety__load_scenario_skill, mcp__safety__submit_safety_report]
5. 跑 `query()`，drain 整个 stream（异常用 SDK 自带的 CLI/Process 错误抽出来）
6. 从 sink 取报告；sink 为空 → 抛 LLMCallError（Agent 没调 submit）
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    Message,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
)

from app.config import Settings
from app.errors import LLMCallError, LLMTimeoutError
from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder
from app.safety_agent.tools import SAFETY_MCP_SERVER_NAME, build_safety_tools
from app.schemas.report_v2 import ReportV2Payload

logger = logging.getLogger(__name__)

# allowed_tools 必须包含 Read（Agent 用它把临时图片文件读进 context），
# 以及两个自定义工具的 mcp__前缀全名（SDK 把工具名 namespace 化为 mcp__<server>__<name>）。
_LOAD_TOOL_FQN = f"mcp__{SAFETY_MCP_SERVER_NAME}__load_scenario_skill"
_SUBMIT_TOOL_FQN = f"mcp__{SAFETY_MCP_SERVER_NAME}__submit_safety_report"


class AgentRunStats:
    """单次分析的统计信息（plan §3.3 日志埋点）。"""

    def __init__(self) -> None:
        self.tool_calls: int = 0
        self.scenarios_loaded: list[str] = []
        self.elapsed_ms: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost_usd: float = 0.0


async def _drain(
    stream: AsyncIterator[Message],
    stats: AgentRunStats,
) -> None:
    """消费整个消息流；顺路抽统计 + 记 tool 调用。"""
    async for msg in stream:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    stats.tool_calls += 1
                    if block.name == _LOAD_TOOL_FQN:
                        sid = (block.input or {}).get("scenario_id", "")
                        if sid:
                            stats.scenarios_loaded.append(sid)
                elif isinstance(block, TextBlock):
                    # Agent 的自由文本（思考过程 / CoT 痕迹）；不打印，避免噪音
                    pass
        elif isinstance(msg, ResultMessage):
            # ResultMessage 携带 token 统计；字段名跨版本可能漂移，做兜底
            usage: Any = getattr(msg, "usage", None) or {}
            stats.input_tokens = int(usage.get("input_tokens", 0) or 0)
            stats.output_tokens = int(usage.get("output_tokens", 0) or 0)
            stats.cost_usd = float(getattr(msg, "total_cost_usd", 0.0) or 0.0)


async def analyze_image(
    image_bytes: bytes,
    settings: Settings,
    skill_loader: SkillLoader,
    extra_context: str = "",
) -> tuple[ReportV2Payload, AgentRunStats]:
    """跑一次 v2 分析。返回 (报告, 统计)。

    Raises:
        LLMTimeoutError: 超过 settings.agent_timeout_seconds 仍未收到 submit
        LLMCallError: SDK 异常 / Agent 没调 submit / schema 一直校验不过
    """
    stats = AgentRunStats()
    sink: list[ReportV2Payload] = []
    tools = build_safety_tools(skill_loader, sink)
    mcp_server = create_sdk_mcp_server(
        name=SAFETY_MCP_SERVER_NAME, version="1.0.0", tools=tools
    )

    builder = PromptBuilder(skill_loader)
    system_prompt = builder.build_system_prompt()
    user_intro = builder.build_initial_user_message(extra_context)

    # 临时文件：Agent 用 Read 工具读。后缀按上游探测的 content_type 给，但
    # FastAPI 上游已限制为 jpeg/png，统一用 .jpg 足够；模型不挑后缀。
    tmp_path: Path | None = None
    started = time.monotonic()
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name).resolve()

        composed_prompt = (
            f"{user_intro}\n\n"
            f"图片路径：{tmp_path}\n"
            f"请先用 Read 工具读取这张图片，再按上述流程逐步分析。"
        )

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            model=settings.agent_model,
            # 生产环境优先复用系统已登录的 Claude CLI，避免 SDK bundled CLI
            # 在部分版本组合下出现 stream-json 协议异常（error: "success"）。
            cli_path=settings.claude_cli_path,
            mcp_servers={SAFETY_MCP_SERVER_NAME: mcp_server},
            allowed_tools=["Read", _LOAD_TOOL_FQN, _SUBMIT_TOOL_FQN],
            max_turns=settings.agent_max_turns,
            permission_mode="bypassPermissions",
        )

        try:
            await asyncio.wait_for(
                _drain(query(prompt=composed_prompt, options=options), stats),
                timeout=settings.agent_timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMTimeoutError(
                f"v2 Agent 分析超时 (>{settings.agent_timeout_seconds}s)"
            ) from exc
        except ClaudeSDKError as exc:
            raise LLMCallError(f"Claude Agent SDK 调用失败: {exc}") from exc

        if not sink:
            raise LLMCallError(
                "Agent 结束分析但未调用 submit_safety_report —— 无最终报告。"
                f" tool_calls={stats.tool_calls}"
            )

        stats.elapsed_ms = int((time.monotonic() - started) * 1000)
        report = sink[-1]  # 取最新一次提交，sink 通常只有一项

        logger.info(
            "v2 analysis done: tool_calls=%d scenarios=%s findings=%d elapsed_ms=%d "
            "tokens=%d/%d cost=%.4f",
            stats.tool_calls,
            stats.scenarios_loaded,
            len(report.findings),
            stats.elapsed_ms,
            stats.input_tokens,
            stats.output_tokens,
            stats.cost_usd,
        )
        return report, stats
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
