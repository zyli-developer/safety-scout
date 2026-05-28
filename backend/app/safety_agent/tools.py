"""v2 Agent 的 in-process MCP tool。

工厂 `build_safety_tools(loader, sink)` 当前只返回一个 SdkMcpTool：
- `submit_safety_report(report_json)` —— Agent 提交最终结构化报告

`sink` 是一个调用方持有的列表（容量 0/1）：submit 校验通过后把 ReportV2Payload
追加进去，agent.analyze_image 在 query() 流结束后从 sink 里取最终结果。
设计成"列表 sink + 闭包工具"，是因为：
1. SDK 把工具调度到 in-process MCP server，没有官方"返回值给宿主"的通道；
2. 用闭包持有 sink 比线程/contextvar 简单，单元测试也好造桩；
3. 多次 submit 由工具方"拒收第二次"或宿主清空 sink 控制（这里取后者：宿主每次
   分析新建 session）。

历史：原本还有 `load_scenario_skill` 工具供 Agent 按需拉 L2 清单，已下线 ——
12 个场景的 L2 内容现在全部 inline 进 system prompt（PromptBuilder），省 4 个
串行 tool turn 的延迟。`loader` 参数当前未使用但保留，便于将来再加新工具不
破坏调用方签名。

错误处理原则（plan §4.3）：
- JSON 解析失败、schema 校验失败：返 `is_error=True` + 可读修复提示，让 Agent 重提交
- 不要 raise —— SDK 会把异常转成 error message，但消息文本不可控
"""
from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool
from pydantic import ValidationError

from app.safety_agent.loader import SkillLoader
from app.schemas.report_v2 import ReportV2Payload

logger = logging.getLogger(__name__)

# MCP server 命名：Claude SDK 会把工具名暴露成 `mcp__<server>__<tool>`。
# 改名会破坏 ClaudeAgentOptions.allowed_tools 与 prompt 里对工具名的引用。
SAFETY_MCP_SERVER_NAME = "safety"


def _text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    """统一封装 MCP 工具 text 响应。"""
    out: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        out["is_error"] = True
    return out


def build_safety_tools(
    loader: SkillLoader,  # noqa: ARG001 —— 保留参数签名以兼容调用方
    report_sink: list[ReportV2Payload],
) -> list[SdkMcpTool[Any]]:
    """构造 v2 Agent 用的 MCP tool。`report_sink` 必须是调用方传入的可变 list。"""

    @tool(
        name="submit_safety_report",
        description=(
            "提交最终的安全隐患分析报告。"
            "report_json 必须严格符合 output_schema.md 规定的 JSON 结构，"
            "可被 json.loads 解析。完成所有分析步骤后调用此工具结束分析。"
            "若结构不合法将返回错误，必须修正后重新调用此工具。"
        ),
        input_schema={"report_json": str},
    )
    async def submit_safety_report(args: dict[str, Any]) -> dict[str, Any]:
        raw = args.get("report_json", "")
        if not isinstance(raw, str) or not raw.strip():
            logger.warning(
                "v2 submit empty payload",
                extra={"metric": "v2.tool.submit.empty"},
            )
            return _text_result("report_json 必须是非空字符串", is_error=True)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "v2 submit json decode failed",
                extra={
                    "metric": "v2.tool.submit.json_error",
                    "err_msg": exc.msg,
                    "err_lineno": exc.lineno,
                    "err_colno": exc.colno,
                },
            )
            return _text_result(
                f"JSON 解析失败：{exc.msg} (line {exc.lineno} col {exc.colno})。"
                "请输出合法 JSON，不要带 markdown 代码块。",
                is_error=True,
            )
        try:
            payload = ReportV2Payload.model_validate(data)
        except ValidationError as exc:
            # 把第一条错误清晰地告诉 Agent；errors() 自带路径
            errs = exc.errors()[:3]
            lines = [
                f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errs
            ]
            logger.warning(
                "v2 submit schema validation failed",
                extra={
                    "metric": "v2.tool.submit.schema_error",
                    "error_count": len(exc.errors()),
                    "first_loc": ".".join(str(p) for p in exc.errors()[0]["loc"]),
                },
            )
            return _text_result(
                "schema 校验失败，请修正以下问题后重新提交：\n"
                + "\n".join(lines)
                + f"\n(共 {len(exc.errors())} 处错误)",
                is_error=True,
            )

        report_sink.append(payload)
        # plan §3.3 severity 分布：从合法 report 里抽样统计每档隐患数 + 整体风险等级
        sev_counts: dict[str, int] = {"重大": 0, "较大": 0, "一般": 0, "低": 0}
        for f in payload.findings:
            sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        logger.info(
            "v2 submit accepted",
            extra={
                "metric": "v2.tool.submit.accepted",
                "findings_count": len(payload.findings),
                "uncertain_count": len(payload.uncertain),
                "no_findings_count": len(payload.no_findings),
                "overall_risk_level": payload.report_meta.overall_risk_level,
                "severity_distribution": sev_counts,
                "scene_detected": payload.report_meta.scene_detected,
            },
        )
        return _text_result(
            f"报告已接收。发现 {len(payload.findings)} 项隐患，"
            f"{len(payload.uncertain)} 项待复核。分析结束。"
        )

    return [submit_safety_report]
