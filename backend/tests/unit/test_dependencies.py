"""DI 工厂的分支测试 —— LLM_PROVIDER 切换是否真的拿到不同 provider 实例。

不打真子进程 / 真 HTTP；仅验证工厂分支选择正确，且各 provider 是进程单例。
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.dependencies import (
    _build_claude_provider,
    _build_doubao_provider,
    get_llm_provider,
)
from app.llm.claude_cli import ClaudeCLIProvider
from app.llm.doubao import DoubaoProvider


@pytest.fixture(autouse=True)
def _clear_provider_caches() -> None:
    """每个测试前后清掉 provider 的 lru_cache，避免互相干扰。"""
    _build_claude_provider.cache_clear()
    _build_doubao_provider.cache_clear()
    yield
    _build_claude_provider.cache_clear()
    _build_doubao_provider.cache_clear()


def _settings(**overrides: object) -> Settings:
    """构造一个 Settings 实例，跳过 .env 文件。"""
    base: dict[str, object] = {
        "llm_provider": "claude_cli",
        "claude_cli_path": "claude",
        "claude_model": "claude-sonnet-4-5",
        "claude_timeout_seconds": 300,
        "doubao_api_key": "",
        "doubao_model": "",
        "doubao_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "doubao_timeout_seconds": 120,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_default_returns_claude_provider() -> None:
    """LLM_PROVIDER 未设时（默认 claude_cli）应当拿到 ClaudeCLIProvider。"""
    settings = _settings()
    p = get_llm_provider(settings)
    assert isinstance(p, ClaudeCLIProvider)
    assert p.name == "claude_cli"


def test_doubao_returns_doubao_provider() -> None:
    settings = _settings(
        llm_provider="doubao",
        doubao_api_key="test-key",
        doubao_model="ep-test",
    )
    p = get_llm_provider(settings)
    assert isinstance(p, DoubaoProvider)
    assert p.name == "doubao"
    assert p.model_id == "ep-test"


def test_doubao_without_api_key_raises() -> None:
    """选 doubao 但没配 DOUBAO_API_KEY → 启动期 ValueError，请求前就报错。"""
    settings = _settings(llm_provider="doubao", doubao_api_key="", doubao_model="ep")
    with pytest.raises(ValueError, match="DOUBAO_API_KEY"):
        get_llm_provider(settings)


def test_doubao_without_model_raises() -> None:
    settings = _settings(
        llm_provider="doubao", doubao_api_key="key", doubao_model=""
    )
    with pytest.raises(ValueError, match="DOUBAO_MODEL"):
        get_llm_provider(settings)


def test_provider_is_process_singleton() -> None:
    """同一 Settings 配置下，多次 get_llm_provider 应当返回同一实例。"""
    settings = _settings(
        llm_provider="doubao",
        doubao_api_key="key",
        doubao_model="ep-test",
    )
    a = get_llm_provider(settings)
    b = get_llm_provider(settings)
    assert a is b


def test_switch_does_not_affect_claude_path() -> None:
    """切到 doubao 再切回 claude_cli，claude 路径仍应正常拿到 ClaudeCLIProvider
    （证明 doubao 分支不污染 claude_cli 分支）。"""
    s1 = _settings(
        llm_provider="doubao", doubao_api_key="k", doubao_model="ep"
    )
    p1 = get_llm_provider(s1)
    assert isinstance(p1, DoubaoProvider)

    s2 = _settings(llm_provider="claude_cli")
    p2 = get_llm_provider(s2)
    assert isinstance(p2, ClaudeCLIProvider)
