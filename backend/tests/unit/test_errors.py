"""SafetyScoutError 层级 + 子类必填字段。"""

import pytest

from app.errors import (
    InvalidImageError,
    LLMCallError,
    LLMParseError,
    LLMTimeoutError,
    SafetyScoutError,
)


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


def test_llm_call_error():
    err = LLMCallError("subprocess returned 1")
    assert err.code == "LLM_CALL_FAILED"
    assert err.http_status == 502
    assert err.user_message
    assert "subprocess returned 1" in str(err)
    assert isinstance(err, SafetyScoutError)


def test_llm_timeout_error():
    err = LLMTimeoutError("exceeded 120s")
    assert err.code == "LLM_TIMEOUT"
    assert err.http_status == 504
    assert err.user_message
    assert "exceeded 120s" in str(err)
    assert isinstance(err, SafetyScoutError)
