"""v2 主分析入口 —— Claude Agent SDK + 自定义 submit_safety_report 工具路径。

实际 SDK 接口（pip 版 0.2.x）：
- `query(prompt, options)` → AsyncIterator[Message]
- `ClaudeAgentOptions(system_prompt, model, mcp_servers, allowed_tools, thinking, ...)`
- 自定义工具走 `create_sdk_mcp_server` → 工具名暴露为 `mcp__<server>__<tool>`
- `thinking={"type":"enabled","budget_tokens":N}` —— extended thinking 走专门通道

架构演进：
- v0：模型自由打印 JSON → 容易跑偏
- v1：通过 `submit_safety_report` 自定义工具提交 → 多 1 个 turn + 工具结果回 +
  收尾文本 ~14s
- v2（短暂存在）：native structured output (output_format=json_schema) ——
  CLI 注入虚拟工具 `StructuredOutput`。**Sonnet 4.6 不会用该虚拟工具**，
  5 次 retry 全产空 keys=[]、CLI 放弃、整次超时（commit 1db2f31 引入、
  c7e57de 修过、576bf9a 因 Sonnet 不兼容回退到 Opus 仍 ~120s）。
- v3（当前）：回到 submit tool 路径。曾期望借 Sonnet 4.6 输出速率压到 1min 内，
  但实测 Sonnet 在本场景（36k cached system prompt + 多轮 tool + 复杂嵌套 JSON）
  即使 thinking=0 + 400s timeout 都跑不完单图；推测 Sonnet 处理长 cached prompt
  的吞吐显著低于宣传值。当前 **Opus + submit 工具实测 115s，比 v2 (structured
  output + Opus) 还快 ~5s**（少一次 CLI 注入虚拟工具的 round-trip），所以 v3
  也是 Opus baseline 下的最佳架构。Sonnet 切换留待 Anthropic 修复其长 cached
  prompt 吞吐之后再试。

流程：
1. 写图片到临时文件
2. 用 PromptBuilder 拼 system prompt（含全部 12 个场景的 inline L2 清单），
   写到独立的临时文件 → 走 `--system-prompt-file`（绕 Windows cmd 长度限制）
3. 构造 MCP server 含 submit_safety_report 工具
4. allowed_tools = ["Read", mcp__safety__submit_safety_report]
5. 跑 `query()` drain 整个 stream：累计 tool 时间戳、token 统计
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
# 以及自定义工具的 mcp__前缀全名（SDK 把工具名 namespace 化为 mcp__<server>__<name>）。
# `load_scenario_skill` 已下线 —— 12 个场景全部 inline 进 system prompt。
_READ_TOOL = "Read"
_SUBMIT_TOOL_FQN = f"mcp__{SAFETY_MCP_SERVER_NAME}__submit_safety_report"


class AgentRunStats:
    """单次分析的统计信息（plan §3.3 日志埋点）。"""

    def __init__(self) -> None:
        self.tool_calls: int = 0
        # 历史字段：以前由 load_scenario_skill 工具累计；该工具已下线。
        # 现在 service 层从 report.report_meta.scene_detected 填回。
        self.scenarios_loaded: list[str] = []
        self.elapsed_ms: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        # prompt caching 流量 —— 字段名对齐 Anthropic API usage
        # （SDK 把 API 原样的 usage dict 透传到 ResultMessage.usage）。
        self.cache_read_tokens: int = 0
        self.cache_creation_tokens: int = 0
        self.cost_usd: float = 0.0
        # 每次 tool dispatch 记一条 {seq,name,dispatched_ms}。
        # 同一 AssistantMessage 内的多个 ToolUseBlock 共享 dispatched_ms。
        self.tool_call_timings: list[dict[str, Any]] = []


def _short_tool_name(fqn: str) -> str:
    """mcp__safety__submit_safety_report → submit_safety_report；Read → Read。"""
    return fqn.split("__")[-1] if fqn.startswith("mcp__") else fqn


async def _drain(
    stream: AsyncIterator[Message],
    stats: AgentRunStats,
    *,
    t0: float,
) -> None:
    """消费整个消息流；顺路抽统计 + 记 tool 调用 + 打 dispatched_ms 时间戳。

    t0：调用方 time.monotonic() 起算点；tool 时间戳全部以此为基准。
    """
    async for msg in stream:
        if isinstance(msg, AssistantMessage):
            # 整条消息共享一个 dispatched_ms —— 模型一帧批发，SDK 无法再细分
            dispatched_ms = int((time.monotonic() - t0) * 1000)
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    stats.tool_calls += 1
                    stats.tool_call_timings.append({
                        "seq": stats.tool_calls,
                        "name": _short_tool_name(block.name),
                        "dispatched_ms": dispatched_ms,
                    })
                elif isinstance(block, TextBlock):
                    # Agent 的自由文本（思考过程 / CoT 痕迹）；不打印，避免噪音
                    pass
        elif isinstance(msg, ResultMessage):
            # ResultMessage 携带 token 统计；字段名跨版本可能漂移，做兜底
            usage: Any = getattr(msg, "usage", None) or {}
            stats.input_tokens = int(usage.get("input_tokens", 0) or 0)
            stats.output_tokens = int(usage.get("output_tokens", 0) or 0)
            # Anthropic prompt caching 字段（未开 cache 时这两个都是 0/缺失）
            stats.cache_read_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
            stats.cache_creation_tokens = int(
                usage.get("cache_creation_input_tokens", 0) or 0
            )
            stats.cost_usd = float(getattr(msg, "total_cost_usd", 0.0) or 0.0)


def _build_options(
    settings: Settings,
    system_prompt: str | dict[str, Any],
    mcp_server: Any,
) -> ClaudeAgentOptions:
    """组装 ClaudeAgentOptions。抽出来方便单测断言（无副作用纯构造）。

    `system_prompt` 接受两种形式：
    - `str` —— 直接 inline 走 `--system-prompt <string>` CLI 参数
    - `{"type":"file","path":...}` —— 走 `--system-prompt-file <path>`，绕开
      Windows CreateProcessW 32,767 字符命令行上限（inline 12 个场景后 prompt
      达 36k 字符，单条 arg 就超限）。analyze_image 默认走 file 形式。
    """
    opts_kwargs: dict[str, Any] = dict(
        system_prompt=system_prompt,
        model=settings.agent_model,
        # 生产环境优先复用系统已登录的 Claude CLI，避免 SDK bundled CLI
        # 在部分版本组合下出现 stream-json 协议异常（error: "success"）。
        cli_path=settings.claude_cli_path,
        mcp_servers={SAFETY_MCP_SERVER_NAME: mcp_server},
        allowed_tools=[_READ_TOOL, _SUBMIT_TOOL_FQN],
        max_turns=settings.agent_max_turns,
        permission_mode="bypassPermissions",
    )
    # Extended thinking —— 推理 tokens 走专门通道、不计 output_tokens、不影响最终
    # JSON 输出。budget=0 时禁用（便于 A/B 对比"无思考"基线）。
    if settings.agent_thinking_budget_tokens > 0:
        opts_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": settings.agent_thinking_budget_tokens,
        }
    return ClaudeAgentOptions(**opts_kwargs)


async def analyze_image(
    image_bytes: bytes,
    settings: Settings,
    skill_loader: SkillLoader,
    extra_context: str = "",
) -> tuple[ReportV2Payload, AgentRunStats]:
    """跑一次 v2 分析。返回 (报告, 统计)。

    Raises:
        LLMTimeoutError: 超过 settings.agent_timeout_seconds
        LLMCallError: SDK 异常 / Agent 没调 submit_safety_report
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

    # 临时文件：
    # - 图片：Agent 用 Read 工具读
    # - system prompt：写到文件并让 SDK 走 --system-prompt-file 传给 CLI，绕开
    #   Windows CreateProcessW 32,767 字符命令行上限（inline 12 个场景后 prompt
    #   达 36k 字符，单条 arg 就超限会被 Windows 拒绝 spawn，错误被 SDK 翻成
    #   误导性的 "Claude Code not found at: claude"）。
    #   POSIX 系统不受该限制，但走 file 路径不会有副作用，故统一处理。
    tmp_image: Path | None = None
    tmp_sysprompt: Path | None = None
    started = time.monotonic()
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_image = Path(tmp.name).resolve()
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(system_prompt)
            tmp_sysprompt = Path(tmp.name).resolve()

        composed_prompt = (
            f"{user_intro}\n\n"
            f"图片路径：{tmp_image}\n"
            f"请先用 Read 工具读取这张图片，再按上述流程分析。"
        )

        options = _build_options(
            settings,
            {"type": "file", "path": str(tmp_sysprompt)},
            mcp_server,
        )

        try:
            await asyncio.wait_for(
                _drain(query(prompt=composed_prompt, options=options), stats, t0=started),
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
            "v2 analysis done: tool_calls=%d findings=%d elapsed_ms=%d "
            "tokens=%d/%d cache=r%d/w%d cost=%.4f model=%s thinking=%d",
            stats.tool_calls,
            len(report.findings),
            stats.elapsed_ms,
            stats.input_tokens,
            stats.output_tokens,
            stats.cache_read_tokens,
            stats.cache_creation_tokens,
            stats.cost_usd,
            settings.agent_model,
            settings.agent_thinking_budget_tokens,
        )
        return report, stats
    finally:
        for p in (tmp_image, tmp_sysprompt):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
