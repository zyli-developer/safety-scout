"""Skill 库加载器 —— 从 safety_skills/ 读 markdown 并按需缓存。

设计要点：
- 实例持有一份 `_cache: dict[str, str]` —— 进程内多次分析共享同一份内容；
  Settings 单例 + DI 工厂会把 SkillLoader 也做成进程单例（见 dependencies.py）。
- `_read_file` 自动剥离 YAML frontmatter（skill 文件首部的 `---\n...\n---` 元数据），
  避免把 skill_id/version 这种元信息塞进 system prompt 浪费 token。
- 启动时 preload L1 + shared 模块（每次都用），第一次 query 时不必再去打 IO。
- `get_scenario` 返回 None 表示 ID 不存在；上层 tool 把可用列表回喂给 Agent 让它自纠。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# YAML frontmatter 头部：`---\n...\n---\n`（DOTALL 让 `.` 跨行）
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


class SkillLoader:
    """工地安全隐患 Skill 加载器。

    Args:
        skills_root: skill 文件根目录（含 `_index.json`）
    """

    def __init__(self, skills_root: str | Path):
        self.root = Path(skills_root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"safety_skills 根目录不存在: {self.root}")

        self.index = self._load_index()
        self._cache: dict[str, str] = {}
        self._preload_always()

    # ----- 私有 -----

    def _load_index(self) -> dict:
        index_path = self.root / "_index.json"
        with open(index_path, encoding="utf-8") as f:
            return json.load(f)

    def _read_file(self, relative_path: str) -> str:
        """读取并去除 frontmatter；命中缓存直接返回。"""
        if relative_path in self._cache:
            return self._cache[relative_path]

        full_path = self.root / relative_path
        with open(full_path, encoding="utf-8") as f:
            content = f.read()

        content = _FRONTMATTER_RE.sub("", content, count=1)
        self._cache[relative_path] = content.strip()
        return self._cache[relative_path]

    def _preload_always(self) -> None:
        """预热：L1 必查 + 全部 shared 模块。"""
        self._read_file(self.index["l1_core"])
        for shared in self.index["shared_modules"]:
            self._read_file(shared)

    # ----- 对外接口 -----

    @property
    def index_version(self) -> str:
        """skill 库版本号 —— 给质量追踪 (inspection_metrics.skill_index_version) 用。"""
        return self.index.get("version", "unknown")

    def get_l1_checklist(self) -> str:
        """L1 必查清单（每次分析都要注入 system prompt）。"""
        return self._read_file(self.index["l1_core"])

    def get_shared(self, module_name: str) -> str:
        """获取共享模块，传不带后缀的名字，如 'role_definition'。"""
        return self._read_file(f"_shared/{module_name}.md")

    def get_scenario(self, scenario_id: str) -> str | None:
        """按 ID 加载 L2 场景清单；ID 不存在返回 None。"""
        meta = self.get_scenario_metadata(scenario_id)
        if meta is None:
            return None
        return self._read_file(meta["file"])

    def list_scenarios(self) -> list[dict]:
        """列出全部场景元数据 —— 供 Agent 做场景识别。"""
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "trigger_features": s["trigger_features"],
                "priority": s["priority"],
            }
            for s in self.index["scenarios"]
        ]

    def get_scenario_metadata(self, scenario_id: str) -> dict | None:
        """获取场景的注册表元数据（含 file 路径、estimated_tokens 等）。"""
        return next(
            (s for s in self.index["scenarios"] if s["id"] == scenario_id), None
        )
