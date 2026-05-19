"""4 级容错的 LLM JSON 解析。

L1: json.loads 直接吃
L2: regex 抽 { ... } 再 json.loads
L3: reprompt 注入二次纠正
L4: 抛 LLMParseError
"""

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.errors import LLMParseError
from app.schemas.report import ReportPayload

_JSON_OBJ_GREEDY = re.compile(r"\{[\s\S]*\}")
_JSON_OBJ_NONGREEDY = re.compile(r"\{[\s\S]*?\}")
_REPROMPT_TEMPLATE = (
    "你上一次的输出不是合法的 JSON 对象。请只输出符合规定格式的 JSON 对象，"
    "不要附加任何说明、不要用 markdown 代码块包裹。原响应：\n{original}"
)


def _safe_json_loads(s: str) -> dict[str, Any] | None:
    """json.loads 包一层异常 → None；仅当结果是 dict 时返回。"""
    try:
        result = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
    return result if isinstance(result, dict) else None


def _try_validate_payload(data: dict[str, Any]) -> ReportPayload | None:
    """喂 Pydantic 校验；不抛，仅返回 ReportPayload 或 None。"""
    try:
        return ReportPayload(**data)
    except ValidationError:
        return None


def _try_extract_payload(raw: str) -> ReportPayload | None:
    """L1 + L2：从 LLM 原始字符串中提取并校验通过的 ReportPayload。

    候选顺序（每个候选 dict 都跑一遍 Pydantic 校验，只回第一个通过的）：
      1. raw 整体当 JSON 解析
      2. 贪心 regex 抓 `{...}`（覆盖 markdown 包裹 / 前后含说明文本场景）
      3. 非贪心 regex 逐个抓 `{...}`（覆盖 raw 含多个独立 JSON 对象的极端场景）

    校验放进 loop 是关键：避免 regex 误抓到 hazards 数组里的某个内层 `{...}`
    （它自己也是合法 JSON dict），把不完整的 hazard 当成完整报告抛出去。
    """
    candidate = _safe_json_loads(raw)
    if candidate is not None:
        payload = _try_validate_payload(candidate)
        if payload is not None:
            return payload

    for pattern in (_JSON_OBJ_GREEDY, _JSON_OBJ_NONGREEDY):
        for m in pattern.finditer(raw):
            candidate = _safe_json_loads(m.group(0))
            if candidate is None:
                continue
            payload = _try_validate_payload(candidate)
            if payload is not None:
                return payload
    return None


async def parse_report(
    raw: str,
    *,
    reprompt: Callable[[str], Awaitable[str]] | None = None,
) -> ReportPayload:
    """解析 LLM 原始响应为 ReportPayload，走 4 级容错。

    L1 / L2 失败（既 JSON 解析不出，又 / 或 Pydantic 不过）→ 若有 reprompt 回调，
    L3 让模型纠正后再过 L1 / L2；仍失败 → L4 抛 LLMParseError。

    注意：如果 `reprompt` 回调本身抛异常（如 LLM API 超时 / 网络错误），
    该异常会原样向上传播——`parse_report` 只把解析 / 校验失败包装成
    LLMParseError。LLM 传输层故障由上游 provider / 任务执行层处理。
    """
    payload = _try_extract_payload(raw)
    if payload is not None:
        return payload

    if reprompt is None:
        raise LLMParseError(f"无法从 LLM 响应中解析合法 ReportPayload: {raw[:200]}")

    corrected = await reprompt(_REPROMPT_TEMPLATE.format(original=raw[:500]))
    payload = _try_extract_payload(corrected)
    if payload is not None:
        return payload
    raise LLMParseError(f"二次纠正后仍无法解析合法 ReportPayload: {corrected[:200]}")
