"""Doubao Vision provider，走 Volcengine Ark 的 OpenAI 兼容接口。"""

import base64
import time

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.llm.base import RawLLMResponse


class DoubaoProvider:
    name = "doubao"

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model_id = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"

        t0 = time.monotonic()
        resp: ChatCompletion = await self._client.chat.completions.create(
            model=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.2,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        content = resp.choices[0].message.content or ""
        return RawLLMResponse(
            content=content,
            model=resp.model,
            latency_ms=latency_ms,
            provider_payload=resp.model_dump(),
        )
