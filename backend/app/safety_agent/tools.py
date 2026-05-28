"""v2 Agent 的 in-process MCP tools。

两个工厂函数 + 共享的 sink 模式：
- `build_safety_tools(loader, sink)` —— stage 2 用，返回 [submit_safety_report]
- `build_scene_detection_tool(loader, sink)` —— stage 1 用，返回单个
  submit_scene_detection 工具

`sink` 是一个调用方持有的列表（容量 0/1）：工具校验通过后把结果追加进去，
agent.analyze_image 在 query() 流结束后从 sink 里取。
设计成"列表 sink + 闭包工具"，是因为：
1. SDK 把工具调度到 in-process MCP server，没有官方"返回值给宿主"的通道；
2. 用闭包持有 sink 比线程/contextvar 简单，单元测试也好造桩；
3. 多次提交由工具方"拒收第二次"或宿主清空 sink 控制（这里取后者：宿主每个
   stage 新建 sink）。

历史：原本还有 `load_scenario_skill` 工具供 Agent 按需拉 L2 清单，已下线 ——
12 个场景的 L2 内容现在按 stage 1 命中情况 inline 进 stage 2 system prompt
（PromptBuilder.build_system_prompt(scene_ids=...)）。

错误处理原则（plan §4.3）：
- JSON 解析失败、schema 校验失败、参数非法：返 `is_error=True` + 可读修复提示
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


def build_scene_detection_tool(
    loader: SkillLoader,
    scene_sink: list[list[str]],
) -> list[SdkMcpTool[Any]]:
    """Stage 1 用：场景识别工具。模型识别图属于哪几个场景后调此工具提交 ID 列表。

    Args:
        loader: 用来拿合法场景 ID 列表，做"未知 ID"校验
        scene_sink: 验证通过的场景 ID 列表追加到这里（list[list[str]]，宿主取最后一项）

    返回的工具 input schema：`{"scenes": list[str]}`。
    """
    valid_ids = {s["id"] for s in loader.list_scenarios()}

    @tool(
        name="submit_scene_detection",
        description=(
            "提交 Stage 1 识别出的命中场景 ID 列表。"
            "scenes 必须是 list[str]，每个元素是 system prompt「场景目录」里出现过的 ID（如 'S03'）。"
            "提交后立即结束 Stage 1。"
        ),
        input_schema={"scenes": list[str]},
    )
    async def submit_scene_detection(args: dict[str, Any]) -> dict[str, Any]:
        scenes = args.get("scenes")
        if not isinstance(scenes, list) or not all(isinstance(s, str) for s in scenes):
            logger.warning(
                "v2 stage1 scene_detection bad type",
                extra={"metric": "v2.tool.scene_detection.bad_type"},
            )
            return _text_result(
                "scenes 必须是字符串列表，如 ['S03', 'S05']", is_error=True
            )
        # 过滤未知 ID（不直接报错，而是过滤后告知 —— 模型自然下次调整；
        # 全部非法时报 is_error）
        filtered = [s for s in scenes if s in valid_ids]
        unknown = [s for s in scenes if s not in valid_ids]
        if not filtered:
            logger.warning(
                "v2 stage1 scene_detection all_unknown",
                extra={
                    "metric": "v2.tool.scene_detection.all_unknown",
                    "submitted": scenes,
                },
            )
            return _text_result(
                f"提交的场景 ID 全部不在合法列表中：{scenes}。"
                f"合法 ID 见 system prompt「场景目录」，例如 {sorted(valid_ids)[:5]} ...",
                is_error=True,
            )
        scene_sink.append(filtered)
        if unknown:
            logger.info(
                "v2 stage1 scene_detection partial_unknown",
                extra={
                    "metric": "v2.tool.scene_detection.partial_unknown",
                    "accepted": filtered,
                    "ignored": unknown,
                },
            )
        else:
            logger.info(
                "v2 stage1 scene_detection accepted",
                extra={
                    "metric": "v2.tool.scene_detection.accepted",
                    "scenes": filtered,
                },
            )
        return _text_result(
            f"已记录命中场景：{filtered}"
            + (f"（忽略未知 ID：{unknown}）" if unknown else "")
            + "。Stage 1 结束。"
        )

    return [submit_scene_detection]


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
