"""Settings (pydantic-settings) 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings, get_settings


def test_settings_loads_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 清掉所有可能的 env var 干扰，再清掉 .env 文件干扰
    for k in (
        "LLM_PROVIDER",
        "CLAUDE_CLI_PATH",
        "CLAUDE_MODEL",
        "CLAUDE_TIMEOUT_SECONDS",
        "DOUBAO_API_KEY",
        "DOUBAO_MODEL",
        "DOUBAO_BASE_URL",
        "DOUBAO_TIMEOUT_SECONDS",
        "SQLITE_PATH",
        "UPLOAD_DIR",
        "MAX_IMAGE_MB",
        "POLL_INTERVAL_MS",
        "TIMEOUT_MS",
        "BACKEND_HARD_TIMEOUT_S",
        "RATE_LIMIT_PER_MINUTE",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)  # 切到没 .env 的临时目录
    s = Settings()
    # provider 开关默认 claude_cli，保证旧部署不受影响
    assert s.llm_provider == "claude_cli"
    assert s.claude_cli_path == "claude"
    assert s.claude_model == "claude-sonnet-4-5"
    assert s.claude_timeout_seconds == 300
    # Doubao 字段：key 默认空（强制用户填），model/base_url/timeout 都有可用默认
    assert s.doubao_api_key == ""
    assert s.doubao_model == "doubao-1-5-vision-pro-32k-250115"
    assert s.doubao_base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert s.doubao_timeout_seconds == 120
    assert s.backend_hard_timeout_s == 320
    assert s.timeout_ms == 330000  # 必须 > backend_hard_timeout_s*1000
    assert s.max_image_mb == 15
    assert s.rate_limit_per_minute == 10


def test_settings_llm_provider_switch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """LLM_PROVIDER=doubao 应当被接受；非法值应当被 pydantic 拒掉。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "doubao")
    s = Settings()
    assert s.llm_provider == "doubao"


def test_settings_llm_provider_rejects_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """非 claude_cli/doubao 的值 → pydantic ValidationError，启动早失败而不是请求时报错。"""
    from pydantic import ValidationError

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-4-5")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "30")
    s = Settings()
    assert s.claude_model == "claude-opus-4-5"
    assert s.rate_limit_per_minute == 30


def test_get_settings_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()  # 清掉模块级 cache，确保本测试不被上面影响
    a = get_settings()
    b = get_settings()
    assert a is b  # 同一实例
