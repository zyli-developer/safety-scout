"""FakeLLMProvider 行为验证。

覆盖：
- 录像命中 → 返回与磁盘 JSON 严格一致的 RawLLMResponse
- 录像未命中 → FixtureMissingError（带 sha 前缀的可诊断报错）
- 结构性满足 LLMProvider Protocol（不继承也通过 isinstance）
- prompt 参数被忽略（两个不同 prompt 拿到同一份录像）
- 单个目录支持多张图查表
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.llm.base import LLMProvider, RawLLMResponse
from tests.conftest import FakeLLMProvider, FixtureMissingError


def _write_fixture(
    dir_path: Path,
    *,
    image_bytes: bytes,
    content: str,
    model: str = "test-model",
    latency_ms: int = 100,
    provider_payload: dict[str, Any] | None = None,
    name: str = "case.json",
) -> str:
    """工具：写一个 fixture JSON 到 dir_path，返回 image sha。"""
    digest = sha256(image_bytes).hexdigest()
    fixture = {
        "input": {
            "image_sha256": digest,
            "image_path": f"tests/fixtures/images/{name}.jpg",
            "prompt_version": "v1",
            "provider": "claude_cli",
        },
        "output": {
            "content": content,
            "model": model,
            "latency_ms": latency_ms,
            "provider_payload": provider_payload if provider_payload is not None else {},
        },
        "captured_at": "2026-05-19T00:00:00Z",
        "captured_by": "test",
    }
    (dir_path / name).write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    return digest


async def test_replay_returns_recorded_response(tmp_path: Path) -> None:
    """fixture 已录 → analyze 返回 content/model/latency_ms/provider_payload 与录像一致。"""
    image = b"fake-image-bytes-001"
    _write_fixture(
        tmp_path,
        image_bytes=image,
        content='{"plain_warning":"测试"}',
        model="claude-sonnet-4-5",
        latency_ms=42,
        provider_payload={"total_cost_usd": 0.0123, "session_id": "abc"},
        name="case_001.json",
    )

    fake = FakeLLMProvider(tmp_path)
    r = await fake.analyze(image, "any prompt")

    assert isinstance(r, RawLLMResponse)
    assert r.content == '{"plain_warning":"测试"}'
    assert r.model == "claude-sonnet-4-5"
    assert r.latency_ms == 42
    assert r.provider_payload == {"total_cost_usd": 0.0123, "session_id": "abc"}


async def test_missing_fixture_raises(fake_provider: FakeLLMProvider) -> None:
    """空 fixture 目录 + 任意 image bytes → FixtureMissingError。"""
    with pytest.raises(FixtureMissingError) as exc_info:
        await fake_provider.analyze(b"never-seen-bytes", "any")
    # 报错信息含 sha 前缀 + 重录提示，方便定位
    assert "sha" in str(exc_info.value)
    assert "replay_capture" in str(exc_info.value)


def test_satisfies_protocol(fake_provider: FakeLLMProvider) -> None:
    """FakeLLMProvider 不继承 LLMProvider，runtime_checkable Protocol 应当承认它。"""
    assert isinstance(fake_provider, LLMProvider)
    assert fake_provider.name == "fake"
    assert fake_provider.model_id == "fake-replay"


async def test_prompt_argument_ignored(tmp_path: Path) -> None:
    """同一张图配两个截然不同的 prompt，都拿到同一份录像 ——
    fake 的查表只看 image sha，prompt 是 no-op。这是确定性重放的核心语义。
    """
    image = b"deterministic-image"
    _write_fixture(
        tmp_path,
        image_bytes=image,
        content='{"summary":"deterministic"}',
        name="case_det.json",
    )
    fake = FakeLLMProvider(tmp_path)

    r1 = await fake.analyze(image, "prompt version A")
    r2 = await fake.analyze(image, "completely different prompt B with reprompt template")

    assert r1.content == r2.content == '{"summary":"deterministic"}'
    assert r1.model == r2.model
    assert r1.latency_ms == r2.latency_ms


async def test_loads_multiple_fixtures_from_dir(tmp_path: Path) -> None:
    """一个 FakeLLMProvider 实例支持目录里多个 fixture，按各自 sha 查表。"""
    image_a = b"image-alpha"
    image_b = b"image-bravo"
    _write_fixture(
        tmp_path, image_bytes=image_a, content='{"id":"a"}', name="case_a.json"
    )
    _write_fixture(
        tmp_path, image_bytes=image_b, content='{"id":"b"}', name="case_b.json"
    )

    fake = FakeLLMProvider(tmp_path)
    ra = await fake.analyze(image_a, "p")
    rb = await fake.analyze(image_b, "p")

    assert ra.content == '{"id":"a"}'
    assert rb.content == '{"id":"b"}'
