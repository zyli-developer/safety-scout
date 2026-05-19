"""集成测试：slowapi 速率限制（10/min POST /api/v1/inspections）。

覆盖（Phase 2 Task 7 验收）：
1. 第 11 次 POST 在 1 分钟内 → 429 + RATE_LIMITED envelope
2. GET 不受速率限制 → 30 次 404 不会被限
3. 429 响应 shape 与 SafetyScoutError envelope 一致

测试约束：
- slowapi 用模块级 Limiter 单例（app.rate_limit.limiter），计数器跨测试持久；
  必须用 autouse fixture 在每测试前后调 limiter.reset() 清状态，
  否则会被前一个测试的计数污染。
- 复用 test_routes.py 的 _StubProvider + _noop runner 桩，整体路径不打真 LLM。
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_llm_provider
from app.main import create_app
from app.rate_limit import limiter

_VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"x" * 100


class _StubProvider:
    name = "fake"
    model_id = "stub"

    async def analyze(self, image_bytes: bytes, prompt: str) -> Any:
        raise AssertionError("不应被调用（runner 已 noop）")


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    """每个测试前后清 slowapi 计数器，防止跨测试污染。"""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    async def _noop_run(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "app.routes.inspections.inspection_runner.run", _noop_run
    )

    app = create_app()
    app.dependency_overrides[get_llm_provider] = lambda: _StubProvider()

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def _post_one(client: TestClient) -> int:
    """发一次 POST，返回 status_code。"""
    resp = client.post(
        "/api/v1/inspections",
        files={"image": ("t.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
    )
    return resp.status_code


def test_eleventh_post_in_a_minute_returns_429(client: TestClient) -> None:
    """前 10 次 POST 全 202，第 11 次 429 + RATE_LIMITED envelope。"""
    for i in range(10):
        sc = _post_one(client)
        assert sc == 202, f"POST #{i + 1} 应当 202，实际 {sc}"

    resp = client.post(
        "/api/v1/inspections",
        files={"image": ("t.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 429, resp.text
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["user_message"] == "请求过于频繁，请稍后再试"


def test_get_endpoint_not_rate_limited(client: TestClient) -> None:
    """限速只装在 POST 上；GET 30 次都应当 404，不会被 limit。"""
    for _ in range(30):
        resp = client.get("/api/v1/inspections/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


def test_rate_limit_response_shape(client: TestClient) -> None:
    """429 响应必须与 SafetyScoutError envelope shape 一致：{error:{code,message,user_message}}。"""
    for _ in range(10):
        _post_one(client)

    resp = client.post(
        "/api/v1/inspections",
        files={"image": ("t.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 429
    body = resp.json()
    assert set(body.keys()) == {"error"}
    err = body["error"]
    assert set(err.keys()) == {"code", "message", "user_message"}
    assert err["code"] == "RATE_LIMITED"
    assert "rate limit exceeded" in err["message"]
    assert err["user_message"] == "请求过于频繁，请稍后再试"
