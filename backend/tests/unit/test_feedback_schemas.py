"""FeedbackCreate Pydantic 验证规则单测。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.feedback import FeedbackCreate


def test_missed_allows_empty_check_id() -> None:
    """漏报本质就是"没识别到 X"，check_id 留空合法。"""
    f = FeedbackCreate(kind="missed", description="工人没系安全带，模型没看到")
    assert f.check_id is None


def test_missed_allows_explicit_check_id() -> None:
    """漏报也可以给出 check_id —— 比如"S03-A01 的特定子项目漏掉了"。"""
    f = FeedbackCreate(
        kind="missed",
        check_id="S03-A01",
        description="该子项目漏检",
    )
    assert f.check_id == "S03-A01"


def test_false_positive_requires_check_id() -> None:
    """误报必然针对某条 finding —— 没 check_id 不知道反馈谁。"""
    with pytest.raises(ValidationError):
        FeedbackCreate(kind="false_positive", description="模型误判")


def test_bad_action_requires_check_id() -> None:
    """整改建议不可执行也必然针对某条 finding。"""
    with pytest.raises(ValidationError):
        FeedbackCreate(kind="bad_action", description="建议不可执行")


def test_false_positive_with_check_id_ok() -> None:
    f = FeedbackCreate(
        kind="false_positive",
        check_id="B01",
        description="工人其实戴了安全带，模型没看到",
    )
    assert f.kind == "false_positive"
    assert f.check_id == "B01"


def test_invalid_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(kind="other", description="x")  # type: ignore[arg-type]


def test_description_required() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(kind="missed", description="")


def test_description_max_length_enforced() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(kind="missed", description="x" * 501)


def test_description_at_max_length_ok() -> None:
    f = FeedbackCreate(kind="missed", description="x" * 500)
    assert len(f.description) == 500


def test_check_id_max_length_enforced() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(
            kind="false_positive",
            check_id="x" * 33,
            description="ok",
        )
