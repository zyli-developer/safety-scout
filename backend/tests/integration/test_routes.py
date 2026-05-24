"""集成测试：FastAPI 路由 + 全局异常 handler + 多部分上传 + 后台任务。

目标覆盖（Phase 2 Task 5 验收）：
1. POST 成功路径返 202，并把 poll_url/poll_interval_ms/timeout_ms/inspection_id 透传出去
2. POST 收到错误 MIME → 全局 handler 转 400 + INVALID_IMAGE envelope
3. POST 收到超大 payload → 413 + IMAGE_TOO_LARGE envelope
4. POST 后立刻 GET 同一个 id → status=queued（后台 runner 被桩成 noop）
5. GET 不存在的 id → 404 + NOT_FOUND envelope
6. GET /healthz → 200 {"status":"ok"}

测试要点：
- 用 TestClient + dependency_overrides 注入 tmp_path 的 Settings（保证不污染真实
  local_data/uploads）。
- BackgroundTasks 在 TestClient 里会真的在响应返回后跑；为避免它去调真实
  Claude CLI，我们 monkeypatch app.routes.inspections.inspection_runner.run
  为 async noop（runner.run 是 BackgroundTasks 调度的 entry，桩在路由模块的
  binding 上即可）。
- get_llm_provider 也覆盖成会抛的桩，确保没有路径意外调到真实 provider。
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


class _StubProvider:
    """LLMProvider 桩：若被真的调用就抛，保证测试不依赖外部进程。"""

    name = "fake"
    model_id = "stub"

    async def analyze(self, image_bytes: bytes, prompt: str) -> Any:
        raise AssertionError(
            "StubProvider.analyze 不应被调用；"
            "BackgroundTask 已被 monkeypatch 为 noop"
        )


def _set_tmp_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, max_mb: int = 15
) -> None:
    """通过环境变量把 sqlite/upload 引到 tmp_path，并清 get_settings 的 lru_cache。

    必须用 env 而非纯 dependency_overrides —— main.py 的 lifespan 直接调
    get_settings()（不经过 Depends），那条路径无法被 dependency_overrides 拦截，
    init_schema 必须建在 tmp 库里才能让后续的 repo.get/create 看到表。
    """
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_IMAGE_MB", str(max_mb))
    get_settings.cache_clear()


@pytest.fixture
def app_for_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """每个测试单独建 app + tmp sqlite + tmp upload_dir + 桩 provider。"""
    _set_tmp_env(monkeypatch, tmp_path)

    # 桩掉后台 runner：BackgroundTasks 会调它，但我们不想真的跑模型。
    # 桩在路由模块的 binding 上 —— 路由通过 `from app.tasks import inspection_runner`
    # 拿到模块对象，replace 其 .run 属性即可。
    async def _noop_run(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "app.routes.inspections.inspection_runner.run", _noop_run
    )

    app = create_app()
    # 留 provider override：env 没法覆盖（Settings 字段里没有 provider 实例），
    # 而我们要保证 BackgroundTask 真的被跑到时不去碰 Claude CLI 子进程。
    app.dependency_overrides[get_llm_provider] = lambda: _StubProvider()

    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.fixture
def client(app_for_test: Any) -> Iterator[TestClient]:
    # 进入 with 块触发 lifespan（init_schema 建表）。
    with TestClient(app_for_test) as c:
        yield c


# 一个最小合法 JPEG 头 + 填充，足够通过 size 校验且 content_type 决定 MIME。
_VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"x" * 100


def test_post_inspection_returns_202_and_poll_info(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/inspections",
        files={"image": ("test.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert isinstance(body["inspection_id"], str) and len(body["inspection_id"]) > 0
    assert body["poll_url"] == f"/api/v1/inspections/{body['inspection_id']}"
    assert body["poll_interval_ms"] == 2000
    assert body["timeout_ms"] == 330000
    assert body["status"] == "queued"


def test_post_inspection_rejects_invalid_mime(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/inspections",
        files={"image": ("bad.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "INVALID_IMAGE"
    assert "图片格式" in body["error"]["user_message"]


def test_post_inspection_rejects_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """把 max_image_mb 调到 1MB，再传 2MB payload —— 触发 IMAGE_TOO_LARGE。

    不复用 client fixture：那个 fixture 用 15MB 上限，生成 16MB payload 会显著
    拖慢用例（multipart 传输 + base64 in-process）。本测试单独建一个 1MB 上限的
    app。
    """
    _set_tmp_env(monkeypatch, tmp_path, max_mb=1)

    async def _noop_run(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "app.routes.inspections.inspection_runner.run", _noop_run
    )

    app = create_app()
    app.dependency_overrides[get_llm_provider] = lambda: _StubProvider()

    try:
        with TestClient(app) as c:
            # 2 MB payload，触发 IMAGE_TOO_LARGE
            big = b"\xff\xd8\xff\xe0" + b"x" * (2 * 1024 * 1024)
            resp = c.post(
                "/api/v1/inspections",
                files={"image": ("big.jpg", big, "image/jpeg")},
            )
        assert resp.status_code == 413, resp.text
        body = resp.json()
        assert body["error"]["code"] == "IMAGE_TOO_LARGE"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_get_inspection_returns_queued_immediately(client: TestClient) -> None:
    post_resp = client.post(
        "/api/v1/inspections",
        files={"image": ("test.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert post_resp.status_code == 202
    inspection_id = post_resp.json()["inspection_id"]

    get_resp = client.get(f"/api/v1/inspections/{inspection_id}")
    assert get_resp.status_code == 200, get_resp.text
    body = get_resp.json()
    assert body["inspection_id"] == inspection_id
    # runner.run 被桩成 noop —— status 不会被推进，保持 queued。
    assert body["status"] == "queued"
    assert body["report"] is None
    assert body["error"] is None
    assert body["created_at"]
    assert body["updated_at"]


def test_get_inspection_404(client: TestClient) -> None:
    resp = client.get("/api/v1/inspections/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text
    body = resp.json()
    # Phase 3 T0 起：HTTPException 的 detail（约定为 {"error":{...}}）由
    # _http_exception_handler 扁平化到 body 顶层，与 SafetyScoutError envelope
    # 完全一致。前端只解一种 shape body.error.code。
    assert body["error"]["code"] == "NOT_FOUND"
    assert "找不到" in body["error"]["user_message"]


def test_healthz(client: TestClient) -> None:
    resp = client.get("/api/v1/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_post_emits_queued_log_with_inspection_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """运维可见性回归：POST 成功后必须有一条带 inspection_id 的结构化日志。"""
    import logging as _logging

    with caplog.at_level(_logging.INFO, logger="app.routes.inspections"):
        resp = client.post(
            "/api/v1/inspections",
            files={"image": ("test.jpg", _VALID_JPEG_BYTES, "image/jpeg")},
        )
    assert resp.status_code == 202
    inspection_id = resp.json()["inspection_id"]

    queued = [r for r in caplog.records if r.message == "inspection queued"]
    assert queued, "POST 成功后应记录 'inspection queued'"
    assert getattr(queued[0], "inspection_id", None) == inspection_id
    assert getattr(queued[0], "provider", None) == "fake"


def test_get_404_emits_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """GET 404 必须打 warning —— 排查"前端拿到 404"时能从日志反查 id。"""
    import logging as _logging

    with caplog.at_level(_logging.WARNING, logger="app.routes.inspections"):
        resp = client.get(
            "/api/v1/inspections/00000000-0000-0000-0000-000000000000"
        )
    assert resp.status_code == 404
    warnings = [r for r in caplog.records if r.message == "GET /inspections not found"]
    assert warnings, "GET 404 应记录 warning"
    assert getattr(warnings[0], "error_code", None) == "NOT_FOUND"
