"""FastAPI DI 工厂。集中放在这里，便于集成测试 dependency_overrides 注入桩。

要点：
- get_db：per-request sqlite 连接；FastAPI 通过 yield 管理生命周期（响应返回后 close）。
- get_llm_provider：进程单例 ClaudeCLIProvider；用 settings 字段做 lru_cache key
  （Settings 实例本身不 hashable，而我们也想保证 provider 是真正的单例 —— 多次
  Depends(get_llm_provider) 拿到同一实例）。
- 集成测试通过 app.dependency_overrides[get_llm_provider] = lambda: FakeProvider(...)
  注入桩；overrides 优先于真实工厂。
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.claude_cli import ClaudeCLIProvider
from app.storage.db import connect


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    """Per-request 连接。生命周期由 FastAPI 管理（yield + 响应后自动 close）。"""
    conn = connect(settings.sqlite_path)
    try:
        yield conn
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _build_provider(
    cli_path: str, model: str, timeout_seconds: int
) -> ClaudeCLIProvider:
    """私有：用 settings 字段做 cache key（Settings 实例本身不 hashable）。"""
    return ClaudeCLIProvider(
        cli_path=cli_path, model=model, timeout_seconds=timeout_seconds
    )


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    """进程单例 ClaudeCLIProvider。集成测试通过 dependency_overrides 注入桩。"""
    return _build_provider(
        cli_path=settings.claude_cli_path,
        model=settings.claude_model,
        timeout_seconds=settings.claude_timeout_seconds,
    )
