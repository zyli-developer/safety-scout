"""自定义异常层级，全局 handler 把它们映射成 API 错误响应。

Phase 1 只需要 LLMParseError + InvalidImageError；其余 HTTP 时代再补。
"""

from typing import ClassVar


class SafetyScoutError(Exception):
    code: ClassVar[str] = ""
    http_status: ClassVar[int] = 500
    user_message: ClassVar[str] = ""

    def __init__(self, dev_message: str = ""):
        if not self.code or not self.user_message:
            raise NotImplementedError(
                "SafetyScoutError 子类必须定义 code/http_status/user_message"
            )
        super().__init__(dev_message or self.user_message)


class LLMParseError(SafetyScoutError):
    code = "LLM_PARSE_FAILED"
    http_status = 500
    user_message = "AI 分析结果解析失败，请稍后重试"


class InvalidImageError(SafetyScoutError):
    code = "INVALID_IMAGE"
    http_status = 400
    user_message = "图片格式不支持，请上传 jpg / png / webp"
