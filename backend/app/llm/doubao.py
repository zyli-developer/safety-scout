"""Doubao (火山方舟) Vision provider，走 Ark 的 OpenAI 兼容 Chat Completions 接口。

设计要点：
- 不引入 volcengine-python-sdk —— 用 httpx 直调，避免把火山 SDK 语义渗进 provider 实现；
  与 CLAUDE.md「provider 必须可换」对齐（未来要换 DeepSeek 时 endpoint + 请求 shape 一致）。
- Endpoint：`{base_url}/chat/completions`，messages 走多模态 content 数组
  `[{type:"image_url"}, {type:"text"}]`；图片用 base64 data URI 内联（与 OpenAI 完全一致）。
- 强制 `response_format={"type":"json_object"}` 让 Ark 在 chat 层就保证 JSON 输出，
  减轻 app.llm.parser 的兜底压力。
- Latency 取本地壁钟，不依赖 server 端字段（Ark 不返回 duration_ms）。
- 失败映射：HTTP 非 2xx → LLMCallError；httpx.TimeoutException → LLMTimeoutError；
  缺 choices/content → LLMCallError，与 claude_cli 的"envelope 残缺 = call 失败"语义对齐。
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.errors import LLMCallError, LLMTimeoutError
from app.llm.base import RawLLMResponse

logger = logging.getLogger(__name__)

SAFETY_OFFICER_SYSTEM_PROMPT = (
    "你是中国工地安全员，熟悉《建筑施工安全检查标准》(JGJ59-2011) 与"
    "《建筑施工高处作业安全技术规范》(JGJ80-2016) 等住建部规范。"
    "读取用户提供的工地照片，识别现场安全隐患。"
    "只输出符合用户要求的 JSON 对象，不要附加任何说明、不要用 markdown 代码块包裹。"
)


def _detect_image_mime(image_bytes: bytes) -> str:
    """根据 magic bytes 推断 MIME；落到 OpenAI 多模态接口能识别的类型。

    image_service.validate 已经在 HTTP 入口把非法 MIME 挡掉了，这里只是把入口拿到的
    bytes 转回 MIME 拼 data URI（provider 内部并不知道入口 content_type，因此自检）。
    """
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    # 大多数情况是 JPEG（FF D8 FF）；fallback 也给 jpeg —— Ark 容忍 mime 略不精确，
    # 解码失败时会在 HTTP 层报错而不是 silent 错读。
    return "image/jpeg"


class DoubaoProvider:
    """LLMProvider 的火山方舟实现。`name` 与 ModelMeta.provider Literal 对齐。"""

    name: str = "doubao"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
    ):
        if not api_key:
            raise ValueError(
                "DoubaoProvider 需要 doubao_api_key —— "
                "请在 .env 中配置 DOUBAO_API_KEY"
            )
        if not model:
            raise ValueError(
                "DoubaoProvider 需要 doubao_model —— "
                "请在 .env 中配置 DOUBAO_MODEL（火山方舟 endpoint id 或模型名）"
            )

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self.model_id: str = model

        logger.info(
            "DoubaoProvider initialized",
            extra={
                "base_url": self._base_url,
                "model": model,
                "timeout_seconds": timeout_seconds,
            },
        )

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        """POST `{base_url}/chat/completions`，拿 choices[0].message.content。

        Raises:
            LLMTimeoutError: HTTP 调用超过 timeout_seconds。
            LLMCallError: HTTP 非 2xx / 响应缺 choices / content 为空。
        """
        mime = _detect_image_mime(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SAFETY_OFFICER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            # 让 Ark 在 chat 层强制 JSON 对象输出；app.llm.parser 仍兜底解析失败场景。
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/chat/completions"
        logger.info(
            "calling doubao chat/completions",
            extra={
                "url": url,
                "model": self._model,
                "image_bytes": len(image_bytes),
                "image_mime": mime,
                "prompt_chars": len(prompt),
                "timeout_seconds": self._timeout_seconds,
            },
        )

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error(
                "doubao request timed out",
                extra={"timeout_seconds": self._timeout_seconds},
            )
            raise LLMTimeoutError(
                f"Doubao 调用超时 (>{self._timeout_seconds}s)"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("doubao request failed", exc_info=True)
            raise LLMCallError(f"Doubao 请求失败: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code >= 400:
            body_text = resp.text
            logger.error(
                "doubao non-2xx",
                extra={
                    "status_code": resp.status_code,
                    "body": body_text[:1000],
                },
            )
            raise LLMCallError(
                f"Doubao 非 2xx (status={resp.status_code}): {body_text.strip()[:500]}"
            )

        try:
            envelope: dict[str, Any] = resp.json()
        except ValueError as exc:
            raw_text = resp.text
            raise LLMCallError(
                f"Doubao 响应不是合法 JSON: {raw_text[:500]}"
            ) from exc

        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMCallError(
                f"Doubao 响应缺 choices: keys={list(envelope.keys())}"
            )

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise LLMCallError(
                f"Doubao 响应 choices[0].message 缺失: {choices[0]}"
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMCallError(
                f"Doubao 响应 choices[0].message.content 为空或非字符串: "
                f"{type(content).__name__}"
            )

        return RawLLMResponse(
            content=content,
            model=self._model,
            latency_ms=latency_ms,
            provider_payload=envelope,
        )
