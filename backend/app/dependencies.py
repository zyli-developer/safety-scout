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
import time
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


# SkillLoader TTL cache：(skills_root, ttl_s) → (cached_at_monotonic, loader)。
# 替代 @lru_cache 的 "永久缓存" —— 安全工程师改 .md 后 git pull，下次请求 TTL
# 命中重建，无需重启 backend（docs/specs/v2-rollout.md §三 follow-up）。
#
# ttl_s 作为 cache key 一部分：单测可通过改 settings 字段强制不同 ttl 互不污染。
# 进程级，线程安全 trade-off：FastAPI/uvicorn 单 worker + asyncio 模型下读写在
# 同一 event loop 序列化；并发 worker 部署各自一份 cache，TTL 内多重建几次
# 可接受（SkillLoader 构造 ~毫秒级，I/O 主要是首次读 md）。
_skill_loader_cache: dict[tuple[str, int], tuple[float, SkillLoader]] = {}


def _build_skill_loader(skills_root: str, ttl_s: int) -> SkillLoader:
    """TTL-cached factory。ttl_s ≤ 0 时禁用缓存，每次重建。"""
    if ttl_s <= 0:
        return SkillLoader(skills_root)
    key = (skills_root, ttl_s)
    now = time.monotonic()
    entry = _skill_loader_cache.get(key)
    if entry is not None and now - entry[0] < ttl_s:
        return entry[1]
    loader = SkillLoader(skills_root)
    _skill_loader_cache[key] = (now, loader)
    return loader


def _clear_skill_loader_cache() -> None:
    """仅测试用：手动清缓存（绕开 TTL）。"""
    _skill_loader_cache.clear()


def get_skill_loader(settings: Settings = Depends(get_settings)) -> SkillLoader:
    """SkillLoader —— TTL 缓存，按 settings.safety_skills_cache_ttl_s 控制热重载频率。

    集成测试可通过 app.dependency_overrides 注入指向 tmp dir 的桩 loader；
    需要时也可直接 _clear_skill_loader_cache() 强制重建。
    """
    return _build_skill_loader(
        str(Path(settings.safety_skills_root)),
        settings.safety_skills_cache_ttl_s,
    )
