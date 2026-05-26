"""v2 Agent 的两个 in-process MCP tool。

工厂 `build_safety_tools(loader, sink)` 返回一对 SdkMcpTool：
- `load_scenario_skill(scenario_id)` —— Agent 主动加载命中场景的 L2 清单
- `submit_safety_report(report_json)` —— Agent 提交最终结构化报告

`sink` 是一个调用方持有的列表（容量 0/1）：submit 校验通过后把 ReportV2Payload
追加进去，agent.analyze_image 在 query() 流结束后从 sink 里取最终结果。
设计成"列表 sink + 闭包工具"，是因为：
1. SDK 把工具调度到 in-process MCP server，没有官方"返回值给宿主"的通道；
2. 用闭包持有 sink 比线程/contextvar 简单，单元测试也好造桩；
3. 多次 submit 由工具方"拒收第二次"或宿主清空 sink 控制（这里取后者：宿主每次
   分析新建 session）。

错误处理原则（plan §4.3）：
- JSON 解析失败、schema 校验失败：返 `is_error=True` + 可读修复提示，让 Agent 重提交
- ID 不存在：返可用 ID 列表，让 Agent 自纠
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
    loader: SkillLoader,
    report_sink: list[ReportV2Payload],
) -> list[SdkMcpTool[Any]]:
    """构造 v2 Agent 用的两个 MCP tool。`report_sink` 必须是调用方传入的可变 list。"""

    @tool(
        name="load_scenario_skill",
        description=(
            "加载指定场景 ID 的 L2 详细检查清单（Markdown）。"
            "在 Step 2 场景识别完成后，对每个命中场景调用一次。"
            "若 scenario_id 不存在，返回错误及可用 ID 列表。"
        ),
        input_schema={"scenario_id": str},
    )
    async def load_scenario_skill(args: dict[str, Any]) -> dict[str, Any]:
        scenario_id = (args.get("scenario_id") or "").strip()
        content = loader.get_scenario(scenario_id) if scenario_id else None
        if content is None:
            available = [s["id"] for s in loader.list_scenarios()]
            # plan §3.3：场景识别错误率埋点 —— Agent 报错的 scenario_id 通常意味着
            # prompt 里场景目录列得不够清楚，或模型在编造 ID。
            logger.warning(
                "v2 load_scenario_skill unknown id",
                extra={
                    "metric": "v2.tool.load_scenario.unknown_id",
                    "scenario_id": scenario_id,
                },
            )
            return _text_result(
                f"场景 ID {scenario_id!r} 不存在。可用场景: {available}",
                is_error=True,
            )
        meta = loader.get_scenario_metadata(scenario_id)
        assert meta is not None  # get_scenario 已 None-check
        logger.info(
            "v2 load_scenario_skill hit",
            extra={
                "metric": "v2.tool.load_scenario.hit",
                "scenario_id": scenario_id,
                "scenario_name": meta["name"],
            },
        )
        return _text_result(
            f"# 已加载场景 {scenario_id} - {meta['name']}\n\n{content}"
        )

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

    return [load_scenario_skill, submit_safety_report]
