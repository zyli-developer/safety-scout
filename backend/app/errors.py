"""自定义异常层级，全局 handler 把它们映射成 API 错误响应。

Phase 1 覆盖：LLMParseError + InvalidImageError + LLMCallError + LLMTimeoutError。
（后两者由 Claude CLI provider 引入，封装子进程级故障。）
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


class ImageTooLargeError(SafetyScoutError):
    """上传图片超过 Settings.max_image_mb 限制（架构 §4.4：默认 15 MB）。"""

    code = "IMAGE_TOO_LARGE"
    http_status = 413
    user_message = "图片过大（超过 15MB），请重新拍摄或选择更小的图片"


class LLMCallError(SafetyScoutError):
    """LLM 调用层故障：子进程非零退出、envelope `is_error=True`、stdout 不是合法 JSON。

    与 LLMParseError 的区别：LLMParseError 是模型输出内容不能解析成 ReportPayload；
    LLMCallError 是 provider 还没拿到正常的模型输出（CLI 报错 / 网络故障 / 鉴权问题）。
    """

    code = "LLM_CALL_FAILED"
    http_status = 502
    user_message = "AI 服务暂时不可用，请稍后重试"


class LLMTimeoutError(SafetyScoutError):
    """LLM 调用超出配置的 timeout_seconds。子进程已被 kill 并 reap。"""

    code = "LLM_TIMEOUT"
    http_status = 504
    user_message = "AI 分析超时，请稍后重试"
