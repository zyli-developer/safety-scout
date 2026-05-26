"""
Skill 加载器
负责从文件系统读取 skill markdown 文件，并按需提供给 Agent。
"""

import json
import re
from pathlib import Path
from typing import Optional


class SkillLoader:
    """工地安全隐患 Skill 加载器"""

    def __init__(self, skills_root: str):
        """
        Args:
            skills_root: skill 文件根目录路径，如 '/path/to/safety_skills'
        """
        self.root = Path(skills_root)
        self.index = self._load_index()
        self._cache: dict[str, str] = {}
        self._preload_always()

    def _load_index(self) -> dict:
        index_path = self.root / "_index.json"
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_file(self, relative_path: str) -> str:
        """读取文件，并剥离 frontmatter（YAML 头部）"""
        if relative_path in self._cache:
            return self._cache[relative_path]

        full_path = self.root / relative_path
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 剥离 YAML frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)

        self._cache[relative_path] = content.strip()
        return self._cache[relative_path]

    def _preload_always(self):
        """预加载始终需要的模块（L1 + shared）"""
        self._read_file(self.index["l1_core"])
        for shared in self.index["shared_modules"]:
            self._read_file(shared)

    # ----- 对外接口 -----

    def get_l1_checklist(self) -> str:
        """获取 L1 必查清单"""
        return self._read_file(self.index["l1_core"])

    def get_shared(self, module_name: str) -> str:
        """
        获取共享模块
        module_name: 如 'role_definition' / 'output_schema' / 'fatal_warnings' / 'cot_instructions'
        """
        path = f"_shared/{module_name}.md"
        return self._read_file(path)

    def get_scenario(self, scenario_id: str) -> Optional[str]:
        """
        按 ID 加载场景清单
        scenario_id: 如 'S03', 'S05'
        """
        scenario = next(
            (s for s in self.index["scenarios"] if s["id"] == scenario_id),
            None
        )
        if not scenario:
            return None
        return self._read_file(scenario["file"])

    def list_scenarios(self) -> list[dict]:
        """列出所有可用场景（用于 Agent 做场景识别）"""
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "trigger_features": s["trigger_features"],
                "priority": s["priority"]
            }
            for s in self.index["scenarios"]
        ]

    def get_scenario_metadata(self, scenario_id: str) -> Optional[dict]:
        """获取场景元数据"""
        return next(
            (s for s in self.index["scenarios"] if s["id"] == scenario_id),
            None
        )


# 使用示例
if __name__ == "__main__":
    loader = SkillLoader("/path/to/safety_skills")
    
    # 加载 L1
    l1 = loader.get_l1_checklist()
    print(f"L1 清单字符数: {len(l1)}")
    
    # 加载场景
    s03 = loader.get_scenario("S03")
    print(f"S03 字符数: {len(s03)}")
    
    # 列出所有场景
    scenarios = loader.list_scenarios()
    for s in scenarios:
        print(f"{s['id']}: {s['name']}")
