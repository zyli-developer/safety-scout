"""集成测试：FastAPI lifespan 启动期孤儿恢复（架构 §2.6）。

覆盖：
1. 预先往 tmp DB 写 1 条 queued 行 → 启动 app → 该行变 failed，error.code=INTERNAL，
   user_message 是中文重启提示
2. 空 DB 启动不抛、不留下副作用

测试隔离要点：
- 用 monkeypatch.setenv + get_settings.cache_clear() 把 sqlite_path 指向 tmp_path
- 用 dependency_overrides 把 get_llm_provider 替成桩，防止任何路径碰真 Claude CLI
- 进入 with TestClient(app) 块才会触发 lifespan；退出时还原 logging root handlers
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_llm_provider
from app.main import create_app
from app.storage.db import connect, init_schema


class _StubProvider:
    name = "fake"
    model_id = "stub"

    async def analyze(self, image_bytes: bytes, prompt: str) -> Any:
        raise AssertionError("StubProvider.analyze 不应被调用")


def _set_tmp_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    return db_path


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    """lifespan 调 setup_logging 会替换 root handlers；teardown 还原。

    放 autouse，让本文件每个测试自动隔离 —— 否则同 session 后续测试的 caplog/
    capsys 会被我们装的 stdout JsonFormatter handler 干扰。
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers.clear()
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)


def _seed_queued_inspection(db_path: Path, image_path: str = "/tmp/x.jpg") -> str:
    """预先建表 + 插一行 queued。返回 inspection_id。"""
    conn = connect(db_path)
    try:
        init_schema(conn)
        from app.storage import inspection_repo as repo

        return repo.create(conn, image_path)
    finally:
        conn.close()


def test_startup_marks_orphans_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _set_tmp_env(monkeypatch, tmp_path)
    inspection_id = _seed_queued_inspection(db_path)

    app = create_app()
    app.dependency_overrides[get_llm_provider] = lambda: _StubProvider()
    try:
        # 进入 with 块触发 lifespan：init_schema + 孤儿扫描
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/inspections/{inspection_id}")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "failed"
            assert body["error"]["code"] == "INTERNAL"
            assert body["error"]["user_message"] == "服务重启导致任务中断，请重试"
            assert body["report"] is None
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_startup_with_no_orphans_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """空 DB 启动不抛 + 不留下任何 failed/queued 行。"""
    db_path = _set_tmp_env(monkeypatch, tmp_path)

    app = create_app()
    app.dependency_overrides[get_llm_provider] = lambda: _StubProvider()
    try:
        with TestClient(app) as client:
            # health 路径不依赖任何状态，能跑通就说明 lifespan 顺利完成
            resp = client.get("/api/v1/healthz")
            assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    # 直接打开 DB 验证：inspections 表存在（init_schema 跑过）但没有任何行
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT COUNT(*) FROM inspections").fetchone()
        assert rows[0] == 0
    finally:
        conn.close()
