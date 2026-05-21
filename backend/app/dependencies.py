"""FastAPI DI 工厂。集中放在这里，便于集成测试 dependency_overrides 注入桩。

要点：
- get_db：per-request sqlite 连接；FastAPI 通过 yield 管理生命周期（响应返回后 close）。
- get_llm_provider：进程单例 provider；按 settings.llm_provider 二选一
  （claude_cli / doubao），用 settings 字段做 lru_cache key（Settings 实例本身不
  hashable，而我们也想保证 provider 是真正的单例 —— 多次 Depends(get_llm_provider)
  拿到同一实例）。
- 集成测试通过 app.dependency_overrides[get_llm_provider] = lambda: FakeProvider(...)
  注入桩；overrides 优先于真实工厂。
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.claude_cli import ClaudeCLIProvider
from app.llm.doubao import DoubaoProvider
from app.safety_agent.loader import SkillLoader
from app.storage.db import connect


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    """Per-request 连接。生命周期由 FastAPI 管理（yield + 响应后自动 close）。"""
    conn = connect(settings.sqlite_path)
    try:
        yield conn
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _build_claude_provider(
    cli_path: str, model: str, timeout_seconds: int
) -> ClaudeCLIProvider:
    """私有：用 settings 字段做 cache key（Settings 实例本身不 hashable）。"""
    return ClaudeCLIProvider(
        cli_path=cli_path, model=model, timeout_seconds=timeout_seconds
    )


@lru_cache(maxsize=1)
def _build_doubao_provider(
    api_key: str, model: str, base_url: str, timeout_seconds: int
) -> DoubaoProvider:
    return DoubaoProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    """进程单例 LLMProvider。集成测试通过 dependency_overrides 注入桩。

    业务粒度的 if/else：settings.llm_provider 决定走 claude_cli 还是 doubao；
    provider 内部具体模型由各自 *_model 字段控制，这里不关心。
    """
    if settings.llm_provider == "doubao":
        return _build_doubao_provider(
            api_key=settings.doubao_api_key,
            model=settings.doubao_model,
            base_url=settings.doubao_base_url,
            timeout_seconds=settings.doubao_timeout_seconds,
        )
    return _build_claude_provider(
        cli_path=settings.claude_cli_path,
        model=settings.claude_model,
        timeout_seconds=settings.claude_timeout_seconds,
    )


@lru_cache(maxsize=1)
def _build_skill_loader(skills_root: str) -> SkillLoader:
    """私有：用字符串路径做 cache key（Path 也 hashable，但 str 更省事 + 跨平台稳定）。"""
    return SkillLoader(skills_root)


def get_skill_loader(settings: Settings = Depends(get_settings)) -> SkillLoader:
    """进程单例 SkillLoader —— 预热 L1+shared 后被 v2 路由 / runner 共用。

    集成测试可通过 app.dependency_overrides 注入指向 tmp dir 的桩 loader；
    需要时也可直接 _build_skill_loader.cache_clear() 强制重建。
    """
    return _build_skill_loader(str(Path(settings.safety_skills_root)))
