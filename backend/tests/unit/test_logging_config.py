"""JsonFormatter + setup_logging 单元测试。

覆盖：
1. 基础 LogRecord → 单行 JSON，含必有字段（timestamp/level/logger/message）
2. extra={} 业务字段透传到顶层 JSON
3. exc_info 自动序列化为 traceback 字符串

测试隔离要点：每个用例都会改 root logger 的 handlers / level；fixture 保存原状
在 teardown 还原，避免污染同 session 的其他测试（特别是 integration 测试里
TestClient 触发 lifespan 时也会调 setup_logging）。
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from app.logging_config import setup_logging


@pytest.fixture
def isolated_root_logger() -> Iterator[None]:
    """保存/还原 root logger 状态，防止泄漏 handler 到下个测试。"""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers.clear()
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)


def _parse_single_line(captured: str) -> dict[str, object]:
    """capsys 抓到的 stdout 可能含多行；取最后一条非空行并 json.loads。"""
    lines = [ln for ln in captured.strip().splitlines() if ln.strip()]
    assert lines, f"expected at least one log line, got: {captured!r}"
    return json.loads(lines[-1])  # type: ignore[no-any-return]


def test_json_formatter_outputs_valid_json(
    capsys: pytest.CaptureFixture[str], isolated_root_logger: None
) -> None:
    setup_logging("DEBUG")
    logger = logging.getLogger("safety_scout.test.basic")
    logger.info("hello")

    captured = capsys.readouterr().out
    payload = _parse_single_line(captured)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "safety_scout.test.basic"
    assert payload["message"] == "hello"
    # timestamp 是 ISO 8601 UTC，含微秒 + 末尾 Z
    ts = payload["timestamp"]
    assert isinstance(ts, str)
    assert ts.endswith("Z")
    assert "T" in ts


def test_extra_fields_propagated(
    capsys: pytest.CaptureFixture[str], isolated_root_logger: None
) -> None:
    setup_logging("DEBUG")
    logger = logging.getLogger("safety_scout.test.extra")
    logger.info(
        "inspection succeeded",
        extra={"inspection_id": "abc-123", "latency_ms": 5000},
    )

    payload = _parse_single_line(capsys.readouterr().out)
    assert payload["inspection_id"] == "abc-123"
    assert payload["latency_ms"] == 5000
    # 同时保留 message
    assert payload["message"] == "inspection succeeded"


def test_exception_traceback_serialized(
    capsys: pytest.CaptureFixture[str], isolated_root_logger: None
) -> None:
    setup_logging("DEBUG")
    logger = logging.getLogger("safety_scout.test.exc")
    try:
        raise ValueError("boom-detail")
    except ValueError:
        logger.exception("boom")

    payload = _parse_single_line(capsys.readouterr().out)
    exc_text = payload["exception"]
    assert isinstance(exc_text, str)
    assert "Traceback" in exc_text
    assert "ValueError" in exc_text
    assert "boom-detail" in exc_text
