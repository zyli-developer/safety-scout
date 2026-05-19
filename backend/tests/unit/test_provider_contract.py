"""LLMProvider Protocol 的契约测试。

保证未来实现（claude_cli / fake）都符合签名。
"""

import pytest

from app.llm.base import LLMProvider, RawLLMResponse


class _DummyProvider:
    name = "dummy"
    model_id = "dummy-1"

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        return RawLLMResponse(
            content='{"x":1}', model="dummy-1", latency_ms=10, provider_payload={}
        )


def test_dummy_satisfies_protocol():
    """Protocol 是 duck-typed，DummyProvider 不继承也应该符合。"""
    p: LLMProvider = _DummyProvider()  # 不抛 = 符合
    assert p.name == "dummy"


async def test_dummy_returns_correct_shape():
    p = _DummyProvider()
    r = await p.analyze(b"fake-image", "fake-prompt")
    assert isinstance(r, RawLLMResponse)
    assert r.content == '{"x":1}'
    assert r.latency_ms >= 0


def test_raw_response_requires_all_fields():
    """RawLLMResponse 所有字段必填，防止后续遗漏。"""
    with pytest.raises(TypeError):
        RawLLMResponse(content="x")  # 缺其他字段
