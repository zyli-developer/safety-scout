"""Structured JSON logging。

每条日志一行 JSON，字段：
- 必有：timestamp / level / logger / message
- 可选：从 LogRecord 的 extra 透传 — inspection_id / latency_ms / cost_usd /
  model / error_code 等业务字段，无值就不出现（不写 None）
- 异常：如有 exc_info，加 exception 字段（traceback 字符串）

Phase 3 上线可以直接对接任何 log 聚合（每行 valid JSON）。
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# 与业务相关的 LogRecord extra 字段：__dict__ 里出现的就透传出去。
# 不写死 schema —— 让业务代码加新字段时不需要改 formatter。
_RESERVED_LOG_RECORD_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",  # py3.12+
}


class JsonFormatter(logging.Formatter):
    """把 LogRecord 序列化成单行 JSON。

    业务字段通过 logger.info("...", extra={"inspection_id": ..., ...}) 注入；
    formatter 自动把 LogRecord.__dict__ 里非保留字段都摊到顶层 JSON。
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 透传 extra 字段
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_KEYS:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """清空 root handlers，装一个写 stdout 的 JsonFormatter handler。

    生产入口（FastAPI lifespan）启动时调一次；测试代码若需要 capsys 抓 log，
    传 level="DEBUG" 并先调本函数。

    同时接管 uvicorn 的三个 logger（uvicorn / uvicorn.access / uvicorn.error）——
    uvicorn 在启动时给它们装了自己的 plain-text handler 且 propagate=False，
    不接管的话生产 stdout 会一半 JSON、一半文本，日志聚合无法解析。做法：
    清掉它们自带的 handlers + propagate=True，让它们走 root 的 JsonFormatter。
    """
    root = logging.getLogger()
    # 清掉默认 handler 防止双写
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # 接管 uvicorn 自己的 logger，统一为 JSON 输出
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        ulog = logging.getLogger(name)
        ulog.handlers.clear()
        ulog.propagate = True
