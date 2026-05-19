"""应用配置 —— 通过 `pydantic-settings` 从环境变量 / `.env` 加载。

字段对齐 `docs/plans/2026-05-18-架构-design.md` §2.3 的 `Settings` 类，
并融入 Phase 1 退场总结里两个 follow-ups（见 `docs/specs/prompt-poc-notes.md`）：

1. `claude_model` 默认值固定为 **全名** `claude-sonnet-4-5`，不再用 `sonnet` alias —
   Phase 1 实测 alias 在某些登录态下会被路由到 Opus，单次调用成本翻倍且行为不一致。
2. `claude_timeout_seconds` 默认从 180 上调到 300 —— Phase 1 `case_004` 实测耗时 266s；
   配套 `backend_hard_timeout_s=320 > claude_timeout_seconds`、
   `timeout_ms=330000 > backend_hard_timeout_s*1000`，把"模型超时 → stdlib 超时 →
   前端轮询放弃"的三道闸门留出余地，避免前端先于后端放弃。

`get_settings()` 用 `@lru_cache` 保证整个进程拿到同一份 Settings 实例 ——
路由 / DI / 后台 runner 都从这个单一入口取值，单测里需要重置时主动调
`get_settings.cache_clear()`。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行期配置。字段名 = 环境变量名（大写后）。"""

    # === Claude CLI provider ===
    claude_cli_path: str = "claude"
    # 全名，不用 sonnet alias —— Phase 1 实测 alias 会 fallback 到 Opus
    claude_model: str = "claude-sonnet-4-5"
    # 从 Phase 1 的 180 上调；case_004 实测 266s
    claude_timeout_seconds: int = 300

    # === Storage ===
    sqlite_path: str = "local_data/safety_scout.db"
    upload_dir: str = "uploads"

    # === Image upload ===
    max_image_mb: int = 15  # 与架构 §4.4 + .env.example 一致

    # === Async polling（前端用） ===
    poll_interval_ms: int = 2000
    # 前端轮询总时限 > backend_hard_timeout_s * 1000
    timeout_ms: int = 330000

    # === Backend ===
    # > claude_timeout_seconds，留给 stdlib 余地
    backend_hard_timeout_s: int = 320
    rate_limit_per_minute: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """进程单例 Settings —— 路由 / DI / 后台 runner 统一入口。"""
    return Settings()
