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

_JSON_OBJ_PATTERN = re.compile(r"\{[\s\S]*\}")
_REPROMPT_TEMPLATE = (
    "你上一次的输出不是合法的 JSON 对象。请只输出符合规定格式的 JSON 对象，"
    "不要附加任何说明、不要用 markdown 代码块包裹。原响应：\n{original}"
)


def _try_loads(raw: str) -> dict[str, Any] | None:
    """L1 + L2。返回 None 表示都没成功。"""
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        result = None
    if isinstance(result, dict):
        return result
    m = _JSON_OBJ_PATTERN.search(raw)
    if not m:
        return None
    try:
        result = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(result, dict):
        return result
    return None


def _validate(data: dict[str, Any]) -> ReportPayload:
    try:
        return ReportPayload(**data)
    except ValidationError as e:
        raise LLMParseError(f"Pydantic 校验失败: {e}") from e


async def parse_report(
    raw: str,
    *,
    reprompt: Callable[[str], Awaitable[str]] | None = None,
) -> ReportPayload:
    parsed = _try_loads(raw)
    if parsed is not None:
        return _validate(parsed)

    if reprompt is None:
        raise LLMParseError(f"无法从 LLM 响应中解析 JSON: {raw[:200]}")

    corrected = await reprompt(_REPROMPT_TEMPLATE.format(original=raw[:500]))
    parsed = _try_loads(corrected)
    if parsed is None:
        raise LLMParseError(f"二次纠正后仍无法解析: {corrected[:200]}")
    return _validate(parsed)
