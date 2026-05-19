"""inspection_service.run_inspection 编排逻辑单测。

覆盖 5 个场景：
  1. happy path：provider 返回合法 JSON → succeeded + report/meta 落库
  2. LLM 解析错误：原始 + reprompt 都垃圾文本 → failed + LLM_PARSE_FAILED
  3. LLM 超时：provider.analyze 抛 LLMTimeoutError → failed + LLM_TIMEOUT
  4. 未预期异常：provider 抛 ValueError → failed + INTERNAL + 中文 user_message
  5. 信号量并发上限：5 个并发，cap=2 时实际并发不超过 2

刻意不复用 conftest.FakeLLMProvider —— 这里需要按测试控制返回 / 异常 / 计时，
inline stub 更直观，也避免和 fixture 录像耦合。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.errors import LLMTimeoutError
from app.llm.base import RawLLMResponse
from app.schemas.report import Hazard, ModelMeta, ReportPayload
from app.services import inspection as service
from app.storage import inspection_repo as repo
from app.storage.db import connect, init_schema

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _restore_semaphore() -> Iterator[None]:
    """每个测试结束都把模块级信号量还原成默认 cap=2，避免泄漏。"""
    yield
    service.set_semaphore_for_tests(asyncio.Semaphore(2))


def _valid_report_json(inspection_id: str) -> str:
    """构造一个能被 ReportPayload 校验通过的 JSON 字符串。"""
    payload = ReportPayload(
        inspection_id=inspection_id,
        created_at="2026-05-19T08:00:00Z",
        plain_warning="工人未戴安全帽，立刻撤离",
        summary="现场存在 1 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="",
                suggestion="立即责令补齐安全帽",
            )
        ],
        model_meta=ModelMeta(
            provider="claude_cli", model="placeholder", latency_ms=0
        ),
    )
    return payload.model_dump_json()


# ---------------------------------------------------------------------------
# inline provider stubs
# ---------------------------------------------------------------------------


class _StaticProvider:
    """每次 analyze 返回固定 content 的 stub。"""

    name = "claude_cli"
    model_id = "stub-model"

    def __init__(self, content: str, *, latency_ms: int = 1234) -> None:
        self._content = content
        self._latency_ms = latency_ms

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        return RawLLMResponse(
            content=self._content,
            model="stub-model",
            latency_ms=self._latency_ms,
            provider_payload={"total_cost_usd": 0.0123},
        )


class _RaisingProvider:
    """analyze 时直接抛指定异常的 stub。"""

    name = "claude_cli"
    model_id = "stub-model"

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        raise self._exc


# ---------------------------------------------------------------------------
# 1. happy path
# ---------------------------------------------------------------------------


async def test_run_inspection_happy_path(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/a.jpg")
    raw_content = _valid_report_json(inspection_id)
    provider = _StaticProvider(raw_content, latency_ms=4321)

    await service.run_inspection(inspection_id, b"img-bytes", provider, conn)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "succeeded"
    assert row.error_json is None

    assert row.report_json is not None
    restored = ReportPayload.model_validate_json(row.report_json)
    assert restored.inspection_id == inspection_id
    assert restored.hazards[0].category_code == "H9"

    assert row.model_meta_json is not None
    meta = ModelMeta.model_validate_json(row.model_meta_json)
    assert meta.provider == "claude_cli"
    assert meta.model == "stub-model"
    assert meta.latency_ms == 4321


# ---------------------------------------------------------------------------
# 2. LLM parse error: garbage in + garbage reprompt → failed + LLM_PARSE_FAILED
# ---------------------------------------------------------------------------


async def test_run_inspection_llm_parse_error(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/b.jpg")
    # 原始 + reprompt 都返回这串 garbage —— 既不是 JSON，正则也抽不出合法 dict。
    provider = _StaticProvider("garbage text, not JSON at all")

    await service.run_inspection(inspection_id, b"img-bytes", provider, conn)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "failed"
    assert row.report_json is None
    assert row.model_meta_json is None
    assert row.error_json is not None

    err = json.loads(row.error_json)
    assert err["code"] == "LLM_PARSE_FAILED"
    # LLMParseError.user_message 见 app/errors.py
    assert err["user_message"] == "AI 分析结果解析失败，请稍后重试"


# ---------------------------------------------------------------------------
# 3. LLM timeout: provider.analyze 直接抛 LLMTimeoutError
# ---------------------------------------------------------------------------


async def test_run_inspection_llm_timeout(conn: sqlite3.Connection) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/c.jpg")
    provider = _RaisingProvider(LLMTimeoutError("subprocess killed after 300s"))

    await service.run_inspection(inspection_id, b"img-bytes", provider, conn)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "failed"
    err = json.loads(row.error_json or "{}")
    assert err["code"] == "LLM_TIMEOUT"
    assert err["user_message"] == "AI 分析超时，请稍后重试"


# ---------------------------------------------------------------------------
# 4. unexpected exception → INTERNAL + 中文兜底 user_message
# ---------------------------------------------------------------------------


async def test_run_inspection_unexpected_exception_yields_internal_error(
    conn: sqlite3.Connection,
) -> None:
    inspection_id = repo.create(conn, image_path="/tmp/uploads/d.jpg")
    provider = _RaisingProvider(ValueError("boom"))

    await service.run_inspection(inspection_id, b"img-bytes", provider, conn)

    row = repo.get(conn, inspection_id)
    assert row is not None
    assert row.status == "failed"
    err = json.loads(row.error_json or "{}")
    assert err["code"] == "INTERNAL"
    assert err["user_message"] == "服务内部错误，请重试"
    # dev message 应该带异常类型，便于排查
    assert "ValueError" in err["message"]
    assert "boom" in err["message"]


# ---------------------------------------------------------------------------
# 5. semaphore caps concurrent provider calls
# ---------------------------------------------------------------------------


class _CountingProvider:
    """记录同时进入 analyze 的协程数，用于验证信号量是否生效。"""

    name = "claude_cli"
    model_id = "counting-stub"

    def __init__(self, content: str) -> None:
        self._content = content
        self.current = 0
        self.max_concurrent = 0
        self._lock = asyncio.Lock()

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        async with self._lock:
            self.current += 1
            if self.current > self.max_concurrent:
                self.max_concurrent = self.current
        try:
            # 强制重叠：sleep 长于调度切换时间
            await asyncio.sleep(0.1)
        finally:
            async with self._lock:
                self.current -= 1
        return RawLLMResponse(
            content=self._content,
            model="counting-stub",
            latency_ms=100,
            provider_payload={},
        )


async def test_semaphore_caps_concurrent_provider_calls(tmp_path: Path) -> None:
    # 每个并发任务一条独立的 sqlite 连接，避免 stdlib sqlite3 跨线程 / 跨任务限制。
    db_path = tmp_path / "concurrent.db"
    setup_conn = connect(db_path)
    init_schema(setup_conn)
    ids: list[str] = [
        repo.create(setup_conn, image_path=f"/tmp/uploads/{i}.jpg") for i in range(5)
    ]
    setup_conn.close()

    # 显式把 cap 拍到 2（默认也是 2，但这里要保证测试不被未来默认值变动牵动）
    service.set_semaphore_for_tests(asyncio.Semaphore(2))

    provider = _CountingProvider(_valid_report_json(ids[0]))

    async def _one(inspection_id: str) -> None:
        c = connect(db_path)
        try:
            await service.run_inspection(inspection_id, b"img", provider, c)
        finally:
            c.close()

    await asyncio.gather(*(_one(i) for i in ids))

    assert provider.max_concurrent <= 2, (
        f"max_concurrent={provider.max_concurrent} 超过信号量 cap=2"
    )
    # 进一步保证测试本身有意义：5 个 0.1s 串行最少 0.5s，并发应能拉到 ≥ 2
    assert provider.max_concurrent >= 2, (
        f"max_concurrent={provider.max_concurrent} 未达 2，并发未真正发生"
    )

    # 兜底：5 个全跑完且都标 succeeded
    verify_conn = connect(db_path)
    try:
        for i in ids:
            row = repo.get(verify_conn, i)
            assert row is not None
            assert row.status == "succeeded", f"id={i} status={row.status}"
    finally:
        verify_conn.close()
