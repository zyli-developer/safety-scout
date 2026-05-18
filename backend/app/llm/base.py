"""LLMProvider 抽象。

用 Protocol 而不是 ABC，让测试桩 duck-type 通过而不必继承。
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class RawLLMResponse:
    content: str
    model: str
    latency_ms: int
    provider_payload: dict[str, Any]


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model_id: str

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse: ...
