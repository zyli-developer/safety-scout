"""SafetyScoutError 层级 + 子类必填字段。"""

import pytest

from app.errors import InvalidImageError, LLMParseError, SafetyScoutError


def test_subclass_has_required_attrs():
    err = LLMParseError("raw text")
    assert err.code == "LLM_PARSE_FAILED"
    assert err.http_status == 500
    assert err.user_message  # 非空


def test_base_class_not_instantiable_directly():
    """SafetyScoutError 子类必须显式定义 code/http_status/user_message。"""
    with pytest.raises(NotImplementedError):
        SafetyScoutError("x")  # 基类不允许直接实例化


def test_invalid_image_error():
    err = InvalidImageError("png broken")
    assert err.code == "INVALID_IMAGE"
    assert err.http_status == 400
