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

_JSON_OBJ_NONGREEDY = re.compile(r"\{[\s\S]*?\}")
_JSON_OBJ_GREEDY = re.compile(r"\{[\s\S]*\}")
_REPROMPT_TEMPLATE = (
    "你上一次的输出不是合法的 JSON 对象。请只输出符合规定格式的 JSON 对象，"
    "不要附加任何说明、不要用 markdown 代码块包裹。原响应：\n{original}"
)


def _try_loads(raw: str) -> dict[str, Any] | None:
    """L1 + L2。L1 直接 json.loads；L2 先非贪心扫所有候选 {...}，
    都失败再用贪心整体抓。返回 None 表示都没成功或解析结果非 dict。
    """
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    else:
        if isinstance(result, dict):
            return result

    for pattern in (_JSON_OBJ_NONGREEDY, _JSON_OBJ_GREEDY):
        for m in pattern.finditer(raw):
            try:
                result = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
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
    """解析 LLM 原始响应为 ReportPayload，走 4 级容错。

    注意：如果 `reprompt` 回调本身抛异常（如 LLM API 超时 / 网络错误），
    该异常会原样向上传播——`parse_report` 只把解析 / 校验失败包装成
    LLMParseError。LLM 传输层故障由上游 provider / 任务执行层处理。
    """
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
