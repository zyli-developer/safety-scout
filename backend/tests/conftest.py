"""共享测试 fixtures。

提供 FakeLLMProvider —— 按 image SHA-256 查 `tests/fixtures/llm/` 里的录像返回，
集成测试通过 FastAPI `dependency_overrides` 注入它替代真实 LLM provider。
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.llm.base import RawLLMResponse


class FixtureMissingError(LookupError):
    """FakeLLMProvider 找不到对应 image SHA-256 的录像时抛。

    提示信息里带 sha 前缀和重录命令，方便开发者排查。
    """


class FakeLLMProvider:
    """Record-replay 用的 LLMProvider 实现。

    构造时一次性把 `fixture_dir/*.json` 全部装载进内存（按 image SHA-256 建索引），
    `analyze` 时只看 image 字节算 sha 查表 —— prompt 参数被刻意忽略，确保
    "同一张图任意 prompt 都拿到同一份录像"的确定性重放语义（fixture 是按
    `(image, prompt_version)` 录制的，但生产代码里 prompt 已被冻结为模块常量，
    单测里没必要再按 prompt 二维索引）。

    结构性满足 `app.llm.base.LLMProvider` Protocol（`name` + `model_id` + 异步
    `analyze`），无需显式继承。
    """

    name: str = "fake"
    model_id: str = "fake-replay"

    def __init__(self, fixture_dir: Path) -> None:
        self._by_sha: dict[str, dict[str, Any]] = {}
        if fixture_dir.exists():
            for p in sorted(fixture_dir.glob("*.json")):
                data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
                self._by_sha[data["input"]["image_sha256"]] = data["output"]

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        digest = sha256(image_bytes).hexdigest()
        if digest not in self._by_sha:
            raise FixtureMissingError(
                f"未找到 image sha {digest[:12]} 的 LLM 录像。"
                f"跑 python -m scripts.replay_capture 重新录制"
            )
        out = self._by_sha[digest]
        return RawLLMResponse(
            content=out["content"],
            model=out["model"],
            latency_ms=out["latency_ms"],
            provider_payload=out["provider_payload"],
        )


@pytest.fixture
def fake_provider(tmp_path: Path) -> FakeLLMProvider:
    """空 fixture 目录的 FakeLLMProvider；单测可在传入 tmp_path 前先写文件。

    对于需要预置 fixture 内容的测试，建议直接 `FakeLLMProvider(tmp_path)`
    在自己作用域里实例化，便于控制写入顺序。
    """
    return FakeLLMProvider(tmp_path)
