"""端到端集成测试：POST → 后台 runner → GET 轮询 → succeeded / failed。

这是 Phase 2 退出门主条件（plan T8 + T10）：验证 routes / service / runner /
storage / parser / FakeLLMProvider 串起来后整个轮询语义可工作。

测试约束：
- BackgroundTasks 在 TestClient 里走真实路径（不再 noop runner）；用
  FakeLLMProvider 注入到 dependency_overrides 替代真实 Claude CLI。
- inspection_runner.run 自己开一个 sqlite 连接（架构 §2.5）；它打开的是
  Settings.sqlite_path 所指的同一个 tmp DB，所以路由层 POST 落的行能被
  runner 看到。
- TestClient 同步调用会等待 BackgroundTask 跑完才返回响应控制权 ——
  我们仍然在 POST 之后用短轮询 GET 直到状态推进；这样测试对调度时序不脆弱。
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_llm_provider
from app.errors import LLMTimeoutError
from app.llm.base import RawLLMResponse
from app.main import create_app
from app.rate_limit import limiter
from tests.conftest import FakeLLMProvider

# 复用 Phase 1 录的 case_001 fixture（fixtures/llm/case_001_*.json）。
_FIXTURES_DIR_LLM = (
    Path(__file__).resolve().parents[1] / "fixtures" / "llm"
)
_FIXTURES_DIR_IMG = (
    Path(__file__).resolve().parents[1] / "fixtures" / "images"
)
_CASE_001_IMG_PATH = (
    _FIXTURES_DIR_IMG / "case_001_stepladder_over_2_meters.jpg"
)


class _GarbageProvider:
    """模拟 LLM 返垃圾文本 —— parse_report 4 级容错全过不去 → LLMParseError。"""

    name: str = "fake"
    model_id: str = "garbage-stub"

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        return RawLLMResponse(
            content="I cannot analyze this image, please provide more context.",
            model="garbage-stub",
            latency_ms=10,
            provider_payload={},
        )


class _TimeoutProvider:
    """模拟 Claude CLI 超时 —— provider.analyze 直接抛 LLMTimeoutError。"""

    name: str = "fake"
    model_id: str = "timeout-stub"

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        raise LLMTimeoutError("simulated CLI timeout (>300s)")


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    """每测试前后清 slowapi 计数 —— 防止本文件 4 个 POST 互相吃掉配额。"""
    limiter.reset()
    yield
    limiter.reset()


def _build_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: Any,
) -> Iterator[TestClient]:
    """通用 client 构造器：tmp sqlite + 注入 provider。"""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_llm_provider] = lambda: provider

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def _poll_until_done(
    client: TestClient, inspection_id: str, timeout_s: float = 5.0
) -> dict[str, Any]:
    """每 100ms 拉一次 GET，直到 status != queued/processing 或超时。"""
    deadline = time.monotonic() + timeout_s
    last_body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/inspections/{inspection_id}")
        assert resp.status_code == 200, resp.text
        last_body = resp.json()
        if last_body["status"] not in {"queued", "processing"}:
            return last_body
        time.sleep(0.1)
    pytest.fail(
        f"轮询 {timeout_s}s 后状态仍是 {last_body.get('status')!r}；"
        f"完整响应 last_body={last_body}"
    )


def test_happy_path_post_then_poll_to_succeeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST case_001 → BackgroundTask 跑 FakeLLMProvider（命中 fixture）→
    parse_report 通过 → repo.update_succeeded → GET 拿到完整 ReportPayload。"""
    fake = FakeLLMProvider(_FIXTURES_DIR_LLM)
    client_iter = _build_client(tmp_path, monkeypatch, fake)
    client = next(client_iter)
    try:
        image_bytes = _CASE_001_IMG_PATH.read_bytes()
        # 先确认 fixture 确实有这张图（防 fixture 不同步搞砸测试）
        assert sha256(image_bytes).hexdigest() in fake._by_sha, (
            "case_001 fixture 没装载进 FakeLLMProvider；"
            "重跑 scripts/replay_capture 或检查 fixtures/llm/case_001_*.json"
        )

        post = client.post(
            "/api/v1/inspections",
            files={
                "image": (
                    "case_001.jpg",
                    image_bytes,
                    "image/jpeg",
                )
            },
        )
        assert post.status_code == 202, post.text
        inspection_id: str = post.json()["inspection_id"]

        body = _poll_until_done(client, inspection_id)
        assert body["status"] == "succeeded", body
        assert body["error"] is None
        report = body["report"]
        assert report is not None
        assert report["overall_severity"] in {"high", "medium", "low"}
        assert isinstance(report["hazards"], list) and len(report["hazards"]) >= 1
        # H1 高处坠落 是 case_001 的 GT 主隐患（人字梯超 2m）
        codes = [h["category_code"] for h in report["hazards"]]
        assert "H1" in codes, f"case_001 主隐患 H1 缺失：{codes}"
        # model_meta 必须被 service 覆盖（不能是模型自己幻觉的）
        assert report["model_meta"]["provider"] == "fake"
    finally:
        # 触发 _build_client 的 finally（关 TestClient + 清 overrides）
        with pytest.raises(StopIteration):
            next(client_iter)


def test_failure_path_garbage_response_yields_llm_parse_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM 返垃圾 → parse_report 走 reprompt 仍失败 → LLMParseError →
    repo.update_failed → GET 拿到 error envelope。"""
    client_iter = _build_client(tmp_path, monkeypatch, _GarbageProvider())
    client = next(client_iter)
    try:
        image_bytes = _CASE_001_IMG_PATH.read_bytes()
        post = client.post(
            "/api/v1/inspections",
            files={"image": ("x.jpg", image_bytes, "image/jpeg")},
        )
        assert post.status_code == 202
        inspection_id: str = post.json()["inspection_id"]

        body = _poll_until_done(client, inspection_id, timeout_s=10.0)
        assert body["status"] == "failed", body
        assert body["report"] is None
        err = body["error"]
        assert err is not None
        assert err["code"] == "LLM_PARSE_FAILED"
        assert err["user_message"] == "AI 分析结果解析失败，请稍后重试"
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)


def test_failure_path_provider_timeout_yields_llm_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider.analyze 抛 LLMTimeoutError → service 标 failed +
    code=LLM_TIMEOUT、user_message 中文友好。"""
    client_iter = _build_client(tmp_path, monkeypatch, _TimeoutProvider())
    client = next(client_iter)
    try:
        image_bytes = _CASE_001_IMG_PATH.read_bytes()
        post = client.post(
            "/api/v1/inspections",
            files={"image": ("x.jpg", image_bytes, "image/jpeg")},
        )
        assert post.status_code == 202
        inspection_id: str = post.json()["inspection_id"]

        body = _poll_until_done(client, inspection_id)
        assert body["status"] == "failed", body
        err = body["error"]
        assert err is not None
        assert err["code"] == "LLM_TIMEOUT"
        assert err["user_message"] == "AI 分析超时，请稍后重试"
    finally:
        with pytest.raises(StopIteration):
            next(client_iter)
