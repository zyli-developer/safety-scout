"""Image upload 校验 + 落盘。

设计要点（架构 §4.4）：
- 允许 MIME：image/jpeg | image/jpg | image/png | image/webp
- 不压缩 / 不缩放（Phase 1 已决定，保留原图给 LLM 看）
- 大小上限走 Settings.max_image_mb（默认 15）
- 落盘命名 {uuid4}.{ext}，不保留原始文件名（避免路径注入 + 隐私）
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.errors import ImageTooLargeError, InvalidImageError

ALLOWED_MIME: frozenset[str] = frozenset({
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
})

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def validate(content_type: str, size_bytes: int, max_image_mb: int) -> None:
    """对入参快速校验；不通过抛 SafetyScoutError 子类。"""
    if content_type not in ALLOWED_MIME:
        raise InvalidImageError(f"unsupported content_type: {content_type}")
    max_bytes = max_image_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise ImageTooLargeError(
            f"image size {size_bytes} bytes exceeds limit {max_bytes} ({max_image_mb} MB)"
        )


def save(image_bytes: bytes, upload_dir: str | Path, content_type: str) -> Path:
    """把 image_bytes 落到 {upload_dir}/{uuid4}.{ext}，返回绝对路径。

    调用方应当先 validate() 通过再调 save。如果 content_type 不在 _MIME_TO_EXT 里，
    fallback 到 "bin"（理论上 validate 把不合法 MIME 挡掉了，这里只是兜底）。
    """
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    ext = _MIME_TO_EXT.get(content_type, "bin")
    file_path = upload_path / f"{uuid.uuid4()}.{ext}"
    file_path.write_bytes(image_bytes)
    return file_path.resolve()
