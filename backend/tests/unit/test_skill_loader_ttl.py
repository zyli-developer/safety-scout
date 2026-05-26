"""SkillLoader TTL hot-reload 单元测试。

策略：monkeypatch time.monotonic 控制时间流；验证：
- TTL 内多次 build 返同实例
- TTL 过期后 build 返新实例
- ttl_s=0 → 退化为永远重建
- 不同 skills_root 互相独立
- _clear_skill_loader_cache() 强制重建
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from app.dependencies import (
    _build_skill_loader,
    _clear_skill_loader_cache,
)

# 真实 safety_skills 根目录（仓库根/safety_skills），构造 SkillLoader 必需。
# test 文件在 backend/tests/unit/，parents[3] = 仓库根
_SKILLS_ROOT = (
    Path(__file__).resolve().parents[3] / "safety_skills"
)


@pytest.fixture
def fake_time(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """可控时间：返回一个长度 1 list，测试用 [0] = X 推进时间。"""
    clock = [1000.0]

    def now() -> float:
        return clock[0]

    monkeypatch.setattr("app.dependencies.time.monotonic", now)
    _clear_skill_loader_cache()
    yield clock
    _clear_skill_loader_cache()


def test_within_ttl_returns_same_instance(fake_time: list[float]) -> None:
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    fake_time[0] += 30  # < 60s
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    assert a is b


def test_after_ttl_returns_new_instance(fake_time: list[float]) -> None:
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    fake_time[0] += 61  # > 60s
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    assert a is not b


def test_ttl_zero_disables_cache(fake_time: list[float]) -> None:
    """ttl_s=0 → 每次重建，不写 cache。"""
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=0)
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=0)
    assert a is not b


def test_negative_ttl_disables_cache(fake_time: list[float]) -> None:
    """ttl_s<0 同样视为禁用缓存。"""
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=-1)
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=-1)
    assert a is not b


def test_different_ttl_segments_cache(fake_time: list[float]) -> None:
    """ttl 是 cache key 的一部分 —— 不同 ttl 互不污染。"""
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=120)
    assert a is not b


def test_clear_cache_forces_rebuild(fake_time: list[float]) -> None:
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    _clear_skill_loader_cache()
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    assert a is not b


def test_exact_ttl_boundary_treats_as_expired(fake_time: list[float]) -> None:
    """now - cached_at >= ttl_s → 重建（边界条件：严格 < 才命中）。"""
    a = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    fake_time[0] += 60  # 正好等于 ttl_s
    b = _build_skill_loader(str(_SKILLS_ROOT), ttl_s=60)
    assert a is not b
