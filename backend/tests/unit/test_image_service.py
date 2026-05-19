"""services.image：MIME / size 校验 + uuid 命名落盘。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from app.errors import ImageTooLargeError, InvalidImageError
from app.services import image as image_service

_UUID_HEX_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_validate_accepts_allowed_mimes() -> None:
    for mime in ["image/jpeg", "image/jpg", "image/png", "image/webp"]:
        image_service.validate(mime, size_bytes=1024, max_image_mb=15)


def test_validate_rejects_unsupported_mime() -> None:
    with pytest.raises(InvalidImageError):
        image_service.validate("application/pdf", size_bytes=1024, max_image_mb=15)


def test_validate_rejects_oversize() -> None:
    with pytest.raises(ImageTooLargeError):
        image_service.validate(
            "image/jpeg", size_bytes=20 * 1024 * 1024, max_image_mb=15
        )


def test_save_writes_file_and_returns_path(tmp_path: Path) -> None:
    payload = b"\xff\xd8\xff\xe0\x00\x10JFIFfake-jpeg-bytes"
    result_path = image_service.save(payload, tmp_path, "image/jpeg")

    assert result_path.is_absolute()
    assert result_path.exists()
    assert result_path.read_bytes() == payload
    assert result_path.suffix == ".jpg"
    stem = result_path.stem
    assert _UUID_HEX_RE.match(stem), f"filename stem {stem!r} is not a uuid4 hex"
    # 应该是有效的 uuid4
    parsed = uuid.UUID(stem)
    assert parsed.version == 4


def test_save_creates_upload_dir_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()

    result_path = image_service.save(b"png-bytes", nested, "image/png")

    assert nested.is_dir()
    assert result_path.parent.resolve() == nested.resolve()
    assert result_path.suffix == ".png"
    assert result_path.exists()
