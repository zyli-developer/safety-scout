"""v2 主分析入口 —— 用 Claude Agent SDK + native structured output。

实际 SDK 接口（pip 版 0.2.x）：
- `query(prompt, options)` → AsyncIterator[Message]
- `ClaudeAgentOptions(system_prompt, model, allowed_tools, output_format, thinking, ...)`
- `output_format={"type":"json_schema","schema":...}` —— CLI 强制最终回复符合 schema
- `thinking={"type":"enabled","budget_tokens":N}` —— extended thinking 走专门通道，
  推理 tokens 不计 output_tokens、用户不可见

架构演进：
- v0：模型自由打印 JSON → 容易跑偏，被 v1 替代
- v1：通过 `submit_safety_report` 自定义工具提交 → 多 1 个 turn + 工具结果回 +
  收尾文本 ~14s，由 sink+闭包暴露 payload 给宿主
- v2（当前）：native structured output —— CLI 让模型把最终 JSON 通过虚拟工具
  `StructuredOutput` 的 ToolUseBlock.input 回传（不是 TextBlock，也不是
  ResultMessage.result）。省自建工具、省 turn、省 wrap-up。

流程：
1. 写图片到临时文件
2. 用 PromptBuilder 拼 system prompt（含全部 12 个场景的 inline L2 清单），
   写到独立的临时文件 → 走 `--system-prompt-file`（绕 Windows cmd 长度限制）
3. 跑 `query(options=...)` 含 output_format + thinking
4. drain 整个 stream：累计 tool 时间戳、token 统计、捕获 StructuredOutput.input
5. 用 StructuredOutput.input 走 ReportV2Payload.model_validate
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
    query,
)
from pydantic import ValidationError

from app.config import Settings
from app.errors import LLMCallError, LLMTimeoutError
from app.safety_agent.loader import SkillLoader
from app.safety_agent.prompt import PromptBuilder
from app.schemas.report_v2 import ReportV2Payload

logger = logging.getLogger(__name__)

# allowed_tools 只保留 Read —— Agent 用它把临时图片文件读进 context。
# submit_safety_report / load_scenario_skill 均已下线（structured output 取代前者，
# inline skills 取代后者）。
_READ_TOOL = "Read"

# Claude CLI 在 output_format=json_schema 模式下，会用一个内置的"虚拟工具"
# StructuredOutput 把模型的最终 JSON 当作 ToolUseBlock.input 推回来 —— 不是
# 走 TextBlock 也不是 ResultMessage.result。命中这个工具调用 = 拿到最终答案。
_STRUCTURED_OUTPUT_TOOL = "StructuredOutput"


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
        # 同一 AssistantMessage 内的多个 ToolUseBlock 共享 dispatched_ms
        # （SDK 把模型一帧返回的多个 tool 同时 yield，无法细分批内顺序）。
        # `StructuredOutput` 虚拟工具不计入此列表 —— 它是模型的终态答案，不是
        # agentic 工具调用，跟它对比 tool_calls 会带来语义混淆。
        self.tool_call_timings: list[dict[str, Any]] = []
        # structured output 终态：CLI 把模型生成的最终 JSON 放在虚拟工具
        # `StructuredOutput` 的 ToolUseBlock.input 里推回（已是 dict 不需再 parse）。
        # None = 流结束仍未收到 → 视作 LLMCallError。
        self.structured_output: dict[str, Any] | None = None


def _short_tool_name(fqn: str) -> str:
    """mcp__safety__submit_safety_report → submit_safety_report；Read → Read。"""
    return fqn.split("__")[-1] if fqn.startswith("mcp__") else fqn


async def _drain(
    stream: AsyncIterator[Message],
    stats: AgentRunStats,
    *,
    t0: float,
) -> None:
    """消费整个消息流；顺路抽统计 + 记 tool 调用 + 打 dispatched_ms 时间戳 +
    收集最末条 TextBlock（structured output 的最终 JSON 出口）。

    t0：调用方 time.monotonic() 起算点；tool 时间戳全部以此为基准。
    """
    async for msg in stream:
        if isinstance(msg, AssistantMessage):
            # 整条消息共享一个 dispatched_ms —— 模型一帧批发，SDK 无法再细分
            dispatched_ms = int((time.monotonic() - t0) * 1000)
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    # StructuredOutput 是 CLI 在 json_schema 模式注入的虚拟工具，
                    # 拿来传最终 JSON —— 不算业务 agentic tool，单独路径处理。
                    if block.name == _STRUCTURED_OUTPUT_TOOL:
                        if isinstance(block.input, dict):
                            stats.structured_output = block.input
                        continue
                    stats.tool_calls += 1
                    stats.tool_call_timings.append({
                        "seq": stats.tool_calls,
                        "name": _short_tool_name(block.name),
                        "dispatched_ms": dispatched_ms,
                    })
                elif isinstance(block, TextBlock):
                    # 过程文本不影响最终输出（structured output 走 StructuredOutput 工具）；
                    # 这里不做任何收集，避免与 structured_output 出现"双源"歧义
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
) -> ClaudeAgentOptions:
    """组装 ClaudeAgentOptions。抽出来方便单测断言（无副作用纯构造）。

    `system_prompt` 接受两种形式：
    - `str` —— 直接 inline 走 `--system-prompt <string>` CLI 参数
    - `{"type":"file","path":...}` —— 走 `--system-prompt-file <path>`，绕开
      Windows CreateProcessW 32,767 字符命令行上限（inline 12 个场景后 prompt
      达 36k 字符，单条 arg 就超限）。analyze_image 在 Windows 默认走 file 形式。
    """
    opts_kwargs: dict[str, Any] = dict(
        system_prompt=system_prompt,
        model=settings.agent_model,
        # 生产环境优先复用系统已登录的 Claude CLI，避免 SDK bundled CLI
        # 在部分版本组合下出现 stream-json 协议异常（error: "success"）。
        cli_path=settings.claude_cli_path,
        allowed_tools=[_READ_TOOL],
        max_turns=settings.agent_max_turns,
        permission_mode="bypassPermissions",
    )
    # Native structured output —— CLI 强制最终回复符合 ReportV2Payload schema。
    # 当前实现固定开启；config flag 仅作日志标识。
    if settings.agent_use_native_structured_output:
        opts_kwargs["output_format"] = {
            "type": "json_schema",
            "schema": ReportV2Payload.model_json_schema(),
        }
    # Extended thinking —— 推理 tokens 走专门通道，不计 output_tokens、不影响最终
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
        LLMCallError: SDK 异常 / 没收到文本输出 / 最终输出非合法 JSON
    """
    stats = AgentRunStats()

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

        if stats.structured_output is None:
            raise LLMCallError(
                f"Agent 结束分析但未收到 StructuredOutput 工具调用（output_format 模式"
                f" 期望模型通过此虚拟工具回传最终 JSON）。tool_calls={stats.tool_calls}"
            )

        try:
            report = ReportV2Payload.model_validate(stats.structured_output)
        except ValidationError as exc:
            # native structured output 理论上 CLI 已经强制合法，但保留兜底：
            # schema 不匹配（API 版本漂移 / 模型偶发越界）时给清晰错误，不静默吞掉
            errs = exc.errors()[:3]
            lines = [
                f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errs
            ]
            raise LLMCallError(
                "Agent 最终输出未通过 ReportV2Payload 校验：\n"
                + "\n".join(lines)
                + f"\n(共 {len(exc.errors())} 处错误；顶层 keys: "
                + f"{list(stats.structured_output.keys()) if isinstance(stats.structured_output, dict) else 'N/A'})"
            ) from exc

        stats.elapsed_ms = int((time.monotonic() - started) * 1000)

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
