"""DoubaoProvider 行为契约测试。

策略：patch `httpx.AsyncClient.post`，不打真 Ark；验证：
- 请求 URL / headers / payload 结构（image base64 + JSON 强约束）
- 正常 响应解析为 RawLLMResponse
- HTTP 非 2xx / 缺 choices / content 非字符串 三类故障映射 LLMCallError
- httpx.TimeoutException → LLMTimeoutError
- 缺 api_key / 缺 model → 构造期 ValueError
- Protocol 一致性（runtime_checkable）
"""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.errors import LLMCallError, LLMTimeoutError
from app.llm.base import LLMProvider, RawLLMResponse
from app.llm.doubao import DoubaoProvider


def _valid_response(content: str = '{"x":1}') -> dict[str, Any]:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "model": "ep-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def _mock_response(
    json_body: dict[str, Any] | None = None,
    text: str | None = None,
    status_code: int = 200,
) -> MagicMock:
    """造一个 httpx.Response 的 mock。"""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
        resp.text = json.dumps(json_body)
    else:
        resp.json = MagicMock(side_effect=ValueError("not json"))
        resp.text = text or ""
    return resp


@pytest.fixture
def provider() -> DoubaoProvider:
    return DoubaoProvider(
        api_key="test-key",
        model="ep-test",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        timeout_seconds=60,
    )


def test_provider_satisfies_runtime_protocol(provider: DoubaoProvider) -> None:
    assert isinstance(provider, LLMProvider)
    assert provider.name == "doubao"
    assert provider.model_id == "ep-test"


def test_constructor_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="DOUBAO_API_KEY"):
        DoubaoProvider(
            api_key="",
            model="ep-test",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            timeout_seconds=60,
        )


def test_constructor_rejects_empty_model() -> None:
    with pytest.raises(ValueError, match="DOUBAO_MODEL"):
        DoubaoProvider(
            api_key="key",
            model="",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            timeout_seconds=60,
        )


def test_base_url_trailing_slash_stripped() -> None:
    p = DoubaoProvider(
        api_key="k",
        model="m",
        base_url="https://ark.cn-beijing.volces.com/api/v3/",
        timeout_seconds=60,
    )
    assert p._base_url.endswith("/v3")
    assert not p._base_url.endswith("/")


async def test_happy_path_returns_raw_llm_response(provider: DoubaoProvider) -> None:
    body = _valid_response(content='{"summary":"ok"}')
    resp = _mock_response(json_body=body)

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        raw = await provider.analyze(b"\xff\xd8\xff\xe0fake-jpg", "请分析这张工地照片")

    assert isinstance(raw, RawLLMResponse)
    assert raw.content == '{"summary":"ok"}'
    assert raw.model == "ep-test"
    assert raw.latency_ms >= 0
    # provider_payload 应当完整保留 envelope（usage / id 都在里面，便于审计）
    assert raw.provider_payload == body


async def test_request_payload_structure(provider: DoubaoProvider) -> None:
    """关键：URL / Authorization / messages 多模态结构 / response_format 都要到位。"""
    body = _valid_response()
    resp = _mock_response(json_body=body)

    post_mock = AsyncMock(return_value=resp)
    image_bytes = b"\xff\xd8\xff\xe0fake-jpg"
    with patch("app.llm.doubao.httpx.AsyncClient.post", new=post_mock):
        await provider.analyze(image_bytes, "USER_PROMPT_MARKER")

    call = post_mock.call_args
    url = call.args[0] if call.args else call.kwargs["url"]
    assert url == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"

    payload = call.kwargs["json"]
    assert payload["model"] == "ep-test"
    assert payload["response_format"] == {"type": "json_object"}

    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert "工地安全员" in messages[0]["content"]

    user_msg = messages[1]
    assert user_msg["role"] == "user"
    content_parts = user_msg["content"]
    assert content_parts[0]["type"] == "image_url"
    # image 应当编成 data URI，且 base64 内容等于原 bytes
    data_url = content_parts[0]["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    b64 = data_url.split(",", 1)[1]
    assert base64.b64decode(b64) == image_bytes

    assert content_parts[1]["type"] == "text"
    assert content_parts[1]["text"] == "USER_PROMPT_MARKER"


async def test_png_mime_detected(provider: DoubaoProvider) -> None:
    """PNG magic bytes 应当被识别为 image/png。"""
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    resp = _mock_response(json_body=_valid_response())

    post_mock = AsyncMock(return_value=resp)
    with patch("app.llm.doubao.httpx.AsyncClient.post", new=post_mock):
        await provider.analyze(png_bytes, "prompt")

    payload = post_mock.call_args.kwargs["json"]
    data_url = payload["messages"][1]["content"][0]["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")


async def test_webp_mime_detected(provider: DoubaoProvider) -> None:
    """WEBP magic bytes 应当被识别为 image/webp。"""
    webp_bytes = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20
    resp = _mock_response(json_body=_valid_response())

    post_mock = AsyncMock(return_value=resp)
    with patch("app.llm.doubao.httpx.AsyncClient.post", new=post_mock):
        await provider.analyze(webp_bytes, "prompt")

    payload = post_mock.call_args.kwargs["json"]
    data_url = payload["messages"][1]["content"][0]["image_url"]["url"]
    assert data_url.startswith("data:image/webp;base64,")


async def test_http_400_raises_llm_call_error(provider: DoubaoProvider) -> None:
    resp = _mock_response(text="invalid api key", status_code=401)

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    msg = str(exc_info.value)
    assert "401" in msg
    assert "invalid api key" in msg


async def test_http_500_raises_llm_call_error(provider: DoubaoProvider) -> None:
    resp = _mock_response(text="internal error", status_code=500)

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "500" in str(exc_info.value)


async def test_non_json_body_raises_llm_call_error(provider: DoubaoProvider) -> None:
    """2xx 但 body 不是合法 JSON → LLMCallError。"""
    resp = _mock_response(text="<HTML>oops</HTML>", status_code=200)

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "合法 JSON" in str(exc_info.value)


async def test_missing_choices_raises_llm_call_error(provider: DoubaoProvider) -> None:
    resp = _mock_response(json_body={"id": "x", "usage": {}})

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "choices" in str(exc_info.value)


async def test_empty_choices_raises_llm_call_error(provider: DoubaoProvider) -> None:
    resp = _mock_response(json_body={"choices": []})

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "choices" in str(exc_info.value)


async def test_empty_content_raises_llm_call_error(provider: DoubaoProvider) -> None:
    """choices[0].message.content 空字符串也算缺，不放空串进 parser。"""
    body = _valid_response(content="   ")
    resp = _mock_response(json_body=body)

    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(return_value=resp),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "content" in str(exc_info.value)


async def test_timeout_raises_llm_timeout_error(provider: DoubaoProvider) -> None:
    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectTimeout("timed out")),
    ):
        with pytest.raises(LLMTimeoutError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "超时" in str(exc_info.value)


async def test_network_error_raises_llm_call_error(provider: DoubaoProvider) -> None:
    """非 timeout 的 httpx 错误（DNS / 连接重置）→ LLMCallError，不当成 timeout。"""
    with patch(
        "app.llm.doubao.httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("dns")),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "Doubao 请求失败" in str(exc_info.value)
