"""SkillLoader 单元测试。

覆盖：
- 注册表加载（12 个场景、shared/l1 路径正确）
- 文件读取 + frontmatter 剥离
- get_l1_checklist / get_shared / get_scenario / list_scenarios
- 缺失 scenario_id 返回 None（让 tool 层把可用列表回喂给 Agent）
- 缓存命中（同一文件二次读取走内存）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.safety_agent.loader import SkillLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "safety_skills"


@pytest.fixture(scope="module")
def loader() -> SkillLoader:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"safety_skills 未部署到 {SKILLS_ROOT}，跳过 loader 测试")
    return SkillLoader(SKILLS_ROOT)


def test_index_has_12_scenarios(loader: SkillLoader) -> None:
    scenarios = loader.list_scenarios()
    assert len(scenarios) == 12
    ids = {s["id"] for s in scenarios}
    # 文档明确点名最关键的几个；最严格的 S05（临边洞口）必须在
    assert {"S03", "S05", "S07", "S11"}.issubset(ids)


def test_l1_checklist_non_empty(loader: SkillLoader) -> None:
    l1 = loader.get_l1_checklist()
    assert len(l1) > 500  # L1 至少几百字符；过短意味着 frontmatter 剥得太多
    # frontmatter 一定要被剥掉
    assert not l1.startswith("---")


def test_shared_modules_loadable(loader: SkillLoader) -> None:
    for name in (
        "role_definition",
        "cot_instructions",
        "fatal_warnings",
        "major_hazard_judgment",
        "output_schema",
    ):
        content = loader.get_shared(name)
        assert content, f"shared/{name} 内容为空"
        assert not content.startswith("---")


def test_get_scenario_known(loader: SkillLoader) -> None:
    s03 = loader.get_scenario("S03")
    assert s03 is not None
    assert len(s03) > 500
    # 落地式脚手架核心关键词应该出现
    assert "脚手架" in s03


def test_get_scenario_unknown_returns_none(loader: SkillLoader) -> None:
    assert loader.get_scenario("S99") is None
    assert loader.get_scenario("") is None


def test_scenario_metadata_shape(loader: SkillLoader) -> None:
    meta = loader.get_scenario_metadata("S05")
    assert meta is not None
    assert meta["id"] == "S05"
    assert "file" in meta
    assert "trigger_features" in meta


def test_cache_returns_same_object(loader: SkillLoader) -> None:
    """缓存命中应返回同一对象引用 —— 避免重复 IO。"""
    a = loader.get_l1_checklist()
    b = loader.get_l1_checklist()
    assert a is b


def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SkillLoader(tmp_path / "does_not_exist")
