"""inspection_service 写 metrics 行为单测 —— 质量追踪 Layer 1 服务层契约。

每次 run_inspection（成功 / 失败 / 超时 / 意外异常）都必须写一行
inspection_metrics（防幸存者偏差）。本测试断言这个不变量。
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.errors import LLMTimeoutError
from app.llm.base import RawLLMResponse
from app.schemas.report import Hazard, ModelMeta, ReportPayload
from app.services import inspection as service
from app.storage import inspection_repo, metrics_repo
from app.storage.db import connect, init_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "test.db"
    c = connect(db_path)
    init_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _restore_semaphore() -> Iterator[None]:
    yield
    service.set_semaphore_for_tests(asyncio.Semaphore(2))


def _valid_report_json(inspection_id: str) -> str:
    payload = ReportPayload(
        inspection_id=inspection_id,
        created_at="2026-05-27T08:00:00Z",
        plain_warning="工人未戴安全帽",
        summary="存在 1 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="JGJ59-2011 第 4.0.2 条",
                suggestion="立即补齐安全帽",
            )
        ],
        model_meta=ModelMeta(provider="claude_cli", model="placeholder", latency_ms=0),
    )
    return payload.model_dump_json()


class _StaticProvider:
    name = "claude_cli"
    model_id = "claude-sonnet-4-5"

    def __init__(self, content: str) -> None:
        self._content = content

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        return RawLLMResponse(
            content=self._content,
            model="claude-sonnet-4-5",
            latency_ms=1234,
            provider_payload={"total_cost_usd": 0.0123},
        )


class _RaisingProvider:
    name = "claude_cli"
    model_id = "claude-sonnet-4-5"

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        raise self._exc


# === 成功 ===


async def test_v1_success_writes_metrics_row(conn: sqlite3.Connection) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/a.jpg")
    provider = _StaticProvider(_valid_report_json(iid))

    await service.run_inspection(iid, b"img-bytes", provider, conn)

    row = metrics_repo.get(conn, iid)
    assert row is not None, "v1 成功路径必须写一行 inspection_metrics"
    assert row["status"] == "succeeded"
    assert row["api_version"] == "v1"
    assert row["prompt_version"]  # 非空（取自 PROMPT_VERSION）
    assert row["model"] == "claude-sonnet-4-5"  # 用 raw.model 覆盖
    assert row["finding_count"] == 1
    assert row["reg_coverage"] == 1.0  # regulation 非空
    # image_sha256 = sha256(b"img-bytes")
    import hashlib
    expected_sha = hashlib.sha256(b"img-bytes").hexdigest()
    assert row["image_sha256"] == expected_sha
    assert row["image_bytes"] == len(b"img-bytes")
    assert row["total_elapsed_ms"] >= 0


# === 失败：LLM 解析失败 ===


async def test_v1_parse_failure_writes_metrics_row(conn: sqlite3.Connection) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/b.jpg")
    provider = _StaticProvider("garbage, not JSON")

    await service.run_inspection(iid, b"img", provider, conn)

    row = metrics_repo.get(conn, iid)
    assert row is not None, "失败路径也必须写指标（防幸存者偏差）"
    assert row["status"] == "failed"
    assert row["error_code"] == "LLM_PARSE_FAILED"
    assert row["finding_count"] == 0
    assert row["severity_dist_json"] is None  # 无 report 可摘
    # 版本指纹必须填（即便失败也要能 group by 分析失败率）
    assert row["api_version"] == "v1"
    assert row["prompt_version"]


# === 超时 ===


async def test_v1_timeout_writes_metrics_row_with_timeout_status(
    conn: sqlite3.Connection,
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/c.jpg")
    provider = _RaisingProvider(LLMTimeoutError("simulated timeout"))

    await service.run_inspection(iid, b"img", provider, conn)

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "timeout", "LLMTimeoutError → status=timeout，而非 failed"
    assert row["error_code"] == "LLM_TIMEOUT"


# === 未预期异常 ===


async def test_v1_unexpected_exception_writes_metrics_row_with_internal(
    conn: sqlite3.Connection,
) -> None:
    iid = inspection_repo.create(conn, image_path="/tmp/d.jpg")
    provider = _RaisingProvider(ValueError("unexpected"))

    await service.run_inspection(iid, b"img", provider, conn)

    row = metrics_repo.get(conn, iid)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error_code"] == "INTERNAL"


# === image_sha256 一致性 ===


async def test_same_image_produces_same_sha(conn: sqlite3.Connection) -> None:
    """同一张图跑两次必须产生相同的 image_sha256（同图复跑分析的基础）。"""
    iid1 = inspection_repo.create(conn, image_path="/tmp/e.jpg")
    iid2 = inspection_repo.create(conn, image_path="/tmp/e.jpg")
    provider = _StaticProvider(_valid_report_json(iid1))

    await service.run_inspection(iid1, b"same-bytes", provider, conn)
    # 第二次的 report id 不一样，但仍是同一张图（同 bytes）
    provider2 = _StaticProvider(_valid_report_json(iid2))
    await service.run_inspection(iid2, b"same-bytes", provider2, conn)

    r1 = metrics_repo.get(conn, iid1)
    r2 = metrics_repo.get(conn, iid2)
    assert r1 is not None and r2 is not None
    assert r1["image_sha256"] == r2["image_sha256"]
