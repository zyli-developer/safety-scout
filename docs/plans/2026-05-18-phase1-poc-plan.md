# Phase 1 · Prompt PoC Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用 5 张真实工地图，验证豆包 Vision 能否在我们的 Prompt 引导下输出符合 `report-schema.md` 的结构化报告；同时把后续 Phase 2/3 都要复用的"LLM 适配层 + 解析容错 + Pydantic schemas + 测试基础设施"建好。

**Architecture:** 严格按 `2026-05-18-架构-design.md` §2 分层布局。Phase 1 只搭"LLM 适配层 + schemas + parser + PoC 脚本 + 测试基础设施"五件子集，不引 FastAPI / SQLite / routes / services / tasks。Doubao 走 OpenAI-compatible 接口（`openai` SDK + 自定义 `base_url`），避免引入完整 Volcengine SDK。

**Tech Stack:** Python 3.11+ / `uv` 包管理 / Pydantic v2 / pytest + pytest-asyncio / openai SDK / python-dotenv / ruff / mypy。

**Upstream specs:**
- `docs/specs/hazards.md` (H1-H10 枚举)
- `docs/specs/report-schema.md` (报告 JSON 契约)
- `docs/plans/2026-05-18-架构-design.md` §2, §5

---

## 重要前置说明

**本计划混合"代码任务"与"用户参与任务"**：

| 类型 | 谁做 | 例 |
| --- | --- | --- |
| 代码 / 测试 | 助手（subagent / 主会话） | 写 parser、写 schemas、写测试 |
| 凭证 / 真实数据 | 用户 | 申请豆包 API key、提供 5 张样图 |
| 主观判断 | 用户 | 评判报告"像不像安全员写的"、A/B 实验结论 |

每个 task 标注 **[代码]** / **[用户]** / **[混合]**。

**测试硬规则**（[[feedback-phase-unit-tests]]）：phase 退出时 `pytest backend/` 必须 **0 failed / 0 skipped**。任何"先 skip 等会儿补"的诱惑直接驳回。

---

## 任务依赖图

```
T1 scaffold ─┬─> T2 schemas ──> T3 spec-consistency test ──┐
             │                                              │
             ├─> T4 errors.py ──> T5 parser L1-L4 ──────────┤
             │                                              │
             ├─> T6 LLMProvider Protocol ──> T7 Doubao impl ─┤
             │                                              │
             └─> T8 [用户] API key + sample images          │
                                                            │
                                                            ▼
T9 poc_doubao.py 烟雾测试 ──> T10 Prompt v1 + 5 张图首跑
                                       │
                                       ▼
T11 replay_capture.py + FakeLLMProvider ──> T12 Prompt 迭代到 v2/v3
                                       │
                                       ▼
                              T13 [用户] 压缩 A/B 实验
                                       │
                                       ▼
                        T14 Freeze prompt 到 app/llm/prompt.py
                                       │
                                       ▼
                         T15 Phase 1 退出门验证
```

---

## Task 1: Backend scaffold [代码]

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/.python-version` （内容：`3.11`）
- Create: `backend/app/__init__.py` (空)
- Create: `backend/app/llm/__init__.py` (空)
- Create: `backend/app/schemas/__init__.py` (空)
- Create: `backend/tests/__init__.py` (空)
- Create: `backend/tests/unit/__init__.py` (空)
- Create: `backend/tests/fixtures/.gitkeep`
- Create: `backend/scripts/__init__.py` (空)
- Modify: `.gitignore`（追加 `backend/.venv/`、`backend/local_data/`）

**Step 1: 写 `backend/pyproject.toml`**

```toml
[project]
name = "safety-scout-backend"
version = "0.1.0"
description = "Construction site safety hazard identification backend"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "openai>=1.30",
    "python-dotenv>=1.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "C4"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

**Step 2: 写 `backend/.env.example`**

```
DOUBAO_API_KEY=
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-vision-1.5-pro
```

**Step 3: 写 `backend/.python-version`**

```
3.11
```

**Step 4: 追加 `.gitignore`**

在根目录 `.gitignore` 末尾追加：

```
# ===== Phase 1 Backend =====
backend/.venv/
backend/local_data/
backend/.env
```

**Step 5: 创建空 `__init__.py` 和 `.gitkeep`**

用 Write 工具逐个创建：
- `backend/app/__init__.py` (空字符串)
- `backend/app/llm/__init__.py` (空)
- `backend/app/schemas/__init__.py` (空)
- `backend/tests/__init__.py` (空)
- `backend/tests/unit/__init__.py` (空)
- `backend/scripts/__init__.py` (空)
- `backend/tests/fixtures/.gitkeep` (空)

**Step 6: 安装依赖并验证**

```bash
cd backend && uv venv && uv pip install -e ".[dev]"
```

Expected: `.venv/` 出现；命令成功退出。

```bash
cd backend && .venv/Scripts/python -m pytest --version
```

Expected: 输出 pytest 版本号。

**Step 7: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/.python-version backend/app/ backend/tests/ backend/scripts/ .gitignore
git commit -m "chore: 初始化 backend 工程骨架（Phase 1 子集）"
```

---

## Task 2: Pydantic schemas 对齐 `report-schema.md` [代码]

**Files:**
- Create: `backend/app/schemas/report.py`
- Create: `backend/tests/unit/test_schemas.py`

**Step 1: 写失败测试 `backend/tests/unit/test_schemas.py`**

```python
"""ReportPayload Pydantic 模型对齐 docs/specs/report-schema.md。"""
import pytest
from pydantic import ValidationError
from app.schemas.report import ReportPayload, Hazard, Severity, ModelMeta


def test_minimal_valid_report():
    payload = ReportPayload(
        inspection_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-05-18T08:23:11Z",
        plain_warning="工人未戴安全帽，立刻撤离",
        summary="现场存在 1 项高风险隐患。",
        overall_severity="high",
        hazards=[
            Hazard(
                category_code="H9",
                category_name="个人防护缺失",
                description="2 名工人未佩戴安全帽",
                severity="high",
                regulation="",
                suggestion="立即责令补齐安全帽",
            )
        ],
        model_meta=ModelMeta(provider="doubao", model="doubao-vision-1.5-pro", latency_ms=12345),
    )
    assert payload.overall_severity == "high"
    assert payload.hazards[0].category_code == "H9"


def test_severity_enum_rejects_invalid():
    with pytest.raises(ValidationError):
        Hazard(
            category_code="H1", category_name="高处坠落",
            description="x", severity="critical",  # 非法
            regulation="", suggestion="x",
        )


def test_category_code_must_be_h1_to_h10():
    with pytest.raises(ValidationError):
        Hazard(
            category_code="H11",  # 非法
            category_name="x",
            description="x", severity="high",
            regulation="", suggestion="x",
        )


def test_regulation_can_be_empty_string():
    h = Hazard(
        category_code="H10", category_name="文明施工",
        description="x", severity="low",
        regulation="",  # 允许空
        suggestion="x",
    )
    assert h.regulation == ""


def test_empty_hazards_list_allowed():
    p = ReportPayload(
        inspection_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-05-18T08:23:11Z",
        plain_warning="未识别到隐患",
        summary="现场未识别到明显隐患。",
        overall_severity="low",
        hazards=[],
        model_meta=ModelMeta(provider="doubao", model="x", latency_ms=100),
    )
    assert p.hazards == []
```

**Step 2: 跑测试看它失败**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_schemas.py -v
```

Expected: FAIL（`app.schemas.report` 模块还不存在）。

**Step 3: 写实现 `backend/app/schemas/report.py`**

```python
"""Report payload Pydantic models.

对齐 docs/specs/report-schema.md。任何字段变更必须同 PR 改 spec 文档。
"""
from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
CategoryCode = Literal["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10"]


class Hazard(BaseModel):
    category_code: CategoryCode
    category_name: str
    description: str = Field(max_length=100)
    severity: Severity
    regulation: str = ""
    suggestion: str = Field(max_length=100)


class ModelMeta(BaseModel):
    provider: Literal["doubao", "deepseek", "fake"]
    model: str
    latency_ms: int = Field(ge=0)


class ReportPayload(BaseModel):
    inspection_id: str
    created_at: str
    plain_warning: str = Field(max_length=30)
    summary: str = Field(max_length=100)
    overall_severity: Severity
    hazards: list[Hazard]
    model_meta: ModelMeta
```

**Step 4: 跑测试看它通过**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_schemas.py -v
```

Expected: 5 passed, 0 failed, 0 skipped。

**Step 5: Commit**

```bash
git add backend/app/schemas/report.py backend/tests/unit/test_schemas.py
git commit -m "feat: 添加 ReportPayload Pydantic schema + 单元测试"
```

---

## Task 3: Spec 一致性测试 [代码]

**Files:**
- Modify: `backend/tests/unit/test_schemas.py`

**Step 1: 追加测试**

```python
import re
import json
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "specs" / "report-schema.md"


def _extract_first_json_block(md: str) -> dict:
    """从 markdown 中抽第一个 ```json 代码块并解析。"""
    m = re.search(r"```json\s*\n(.*?)\n```", md, re.DOTALL)
    if not m:
        raise AssertionError("report-schema.md 中找不到 ```json 代码块")
    return json.loads(m.group(1))


def test_spec_example_validates_against_pydantic():
    """报告 schema spec 里的示例 JSON 必须通过 Pydantic 校验。
    spec 改了但 Pydantic 没跟，这个测试会挂。"""
    spec_md = SPEC_PATH.read_text(encoding="utf-8")
    example = _extract_first_json_block(spec_md)
    ReportPayload(**example)  # 不抛 = 通过
```

**Step 2: 跑测试**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_schemas.py::test_spec_example_validates_against_pydantic -v
```

Expected: PASS。如果挂了，**不要**改测试 —— 要么改 `report.py` 让示例通过，要么改 spec 让示例与代码一致（取决于哪边是对的）。

**Step 3: Commit**

```bash
git add backend/tests/unit/test_schemas.py
git commit -m "test: 添加 report-schema.md spec 一致性测试"
```

---

## Task 4: 错误层级 `app/errors.py` [代码]

**Files:**
- Create: `backend/app/errors.py`
- Create: `backend/tests/unit/test_errors.py`

**Step 1: 写失败测试**

```python
"""SafetyScoutError 层级 + 子类必填字段。"""
import pytest
from app.errors import SafetyScoutError, LLMParseError, InvalidImageError


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
```

**Step 2: 跑看失败**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_errors.py -v
```

Expected: FAIL（`app.errors` 不存在）。

**Step 3: 写实现 `backend/app/errors.py`**

```python
"""自定义异常层级，全局 handler 把它们映射成 API 错误响应。
Phase 1 只需要 LLMParseError + InvalidImageError；其余 HTTP 时代再补。"""
from typing import ClassVar


class SafetyScoutError(Exception):
    code: ClassVar[str] = ""
    http_status: ClassVar[int] = 500
    user_message: ClassVar[str] = ""

    def __init__(self, dev_message: str = ""):
        if not self.code or not self.user_message:
            raise NotImplementedError("SafetyScoutError 子类必须定义 code/http_status/user_message")
        super().__init__(dev_message or self.user_message)


class LLMParseError(SafetyScoutError):
    code = "LLM_PARSE_FAILED"
    http_status = 500
    user_message = "AI 分析结果解析失败，请稍后重试"


class InvalidImageError(SafetyScoutError):
    code = "INVALID_IMAGE"
    http_status = 400
    user_message = "图片格式不支持，请上传 jpg / png / webp"
```

**Step 4: 跑测试**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_errors.py -v
```

Expected: 3 passed。

**Step 5: Commit**

```bash
git add backend/app/errors.py backend/tests/unit/test_errors.py
git commit -m "feat: 添加 SafetyScoutError 异常层级（LLMParseError + InvalidImageError）"
```

---

## Task 5: JSON Parser 4 级 fallback [代码]

**Files:**
- Create: `backend/app/llm/parser.py`
- Create: `backend/tests/unit/test_llm_parser.py`
- Create: `backend/tests/fixtures/malformed/`（目录）

**Step 1: 准备畸形输入 fixture**

创建文件 `backend/tests/fixtures/malformed/wrapped_in_markdown.txt`：

````
这是 AI 分析的结果：

```json
{"plain_warning": "测试", "summary": "x", "overall_severity": "low", "inspection_id": "550e8400-e29b-41d4-a716-446655440000", "created_at": "2026-05-18T00:00:00Z", "hazards": [], "model_meta": {"provider": "doubao", "model": "x", "latency_ms": 100}}
```

希望对您有帮助。
````

创建 `backend/tests/fixtures/malformed/garbage_no_json.txt`：

```
I cannot determine the safety hazards in this image without more context. Please provide a clearer view of the construction site.
```

**Step 2: 写测试 `backend/tests/unit/test_llm_parser.py`**

```python
"""parse_report 4 级容错策略。"""
import pytest
from pathlib import Path
from app.llm.parser import parse_report
from app.errors import LLMParseError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "malformed"

MINIMAL_VALID_JSON = """
{
  "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-18T00:00:00Z",
  "plain_warning": "测试",
  "summary": "现场无明显隐患。",
  "overall_severity": "low",
  "hazards": [],
  "model_meta": {"provider": "doubao", "model": "x", "latency_ms": 100}
}
"""


async def test_L1_pure_json():
    """L1：纯 JSON 字符串直接 json.loads 通过。"""
    payload = await parse_report(MINIMAL_VALID_JSON)
    assert payload.overall_severity == "low"


async def test_L2_json_wrapped_in_markdown():
    """L2：JSON 被 ```json fence 包裹 + 前后有文字，regex 抽出来。"""
    raw = FIXTURES.joinpath("wrapped_in_markdown.txt").read_text(encoding="utf-8")
    payload = await parse_report(raw)
    assert payload.plain_warning == "测试"


async def test_L3_reprompt_recovers():
    """L3：第一次响应是垃圾、reprompt 后返回合法 JSON。"""
    call_count = {"n": 0}

    async def fake_reprompt(original: str) -> str:
        call_count["n"] += 1
        return MINIMAL_VALID_JSON

    raw = "I cannot analyze this image."
    payload = await parse_report(raw, reprompt=fake_reprompt)
    assert payload.overall_severity == "low"
    assert call_count["n"] == 1


async def test_L4_raise_after_reprompt_also_fails():
    """L4：reprompt 后还是垃圾，抛 LLMParseError。"""

    async def fake_reprompt(original: str) -> str:
        return "still cannot parse"

    raw = FIXTURES.joinpath("garbage_no_json.txt").read_text(encoding="utf-8")
    with pytest.raises(LLMParseError):
        await parse_report(raw, reprompt=fake_reprompt)


async def test_L4_no_reprompt_provided_and_invalid():
    """无 reprompt 注入时，L1/L2 都不过直接抛 LLMParseError。"""
    raw = "totally invalid"
    with pytest.raises(LLMParseError):
        await parse_report(raw, reprompt=None)


async def test_pydantic_validation_failure_also_raises():
    """JSON 解析通过但 Pydantic 校验失败（如 category_code=H99），抛 LLMParseError。"""
    bad = """
    {
      "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-18T00:00:00Z",
      "plain_warning": "测试",
      "summary": "x",
      "overall_severity": "high",
      "hazards": [{"category_code": "H99", "category_name": "x", "description": "x", "severity": "high", "regulation": "", "suggestion": "x"}],
      "model_meta": {"provider": "doubao", "model": "x", "latency_ms": 100}
    }
    """
    with pytest.raises(LLMParseError):
        await parse_report(bad)
```

**Step 3: 跑看失败**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_llm_parser.py -v
```

Expected: FAIL（`app.llm.parser` 不存在）。

**Step 4: 写实现 `backend/app/llm/parser.py`**

```python
"""4 级容错的 LLM JSON 解析。

L1: json.loads 直接吃
L2: regex 抽 { ... } 再 json.loads
L3: reprompt 注入二次纠正
L4: 抛 LLMParseError
"""
import json
import re
from typing import Awaitable, Callable

from pydantic import ValidationError

from app.errors import LLMParseError
from app.schemas.report import ReportPayload

_JSON_OBJ_PATTERN = re.compile(r"\{[\s\S]*\}")
_REPROMPT_TEMPLATE = (
    "你上一次的输出不是合法的 JSON 对象。请只输出符合规定格式的 JSON 对象，"
    "不要附加任何说明、不要用 markdown 代码块包裹。原响应：\n{original}"
)


def _try_loads(raw: str) -> dict | None:
    """L1 + L2。返回 None 表示都没成功。"""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    m = _JSON_OBJ_PATTERN.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _validate(data: dict) -> ReportPayload:
    try:
        return ReportPayload(**data)
    except ValidationError as e:
        raise LLMParseError(f"Pydantic 校验失败: {e}") from e


async def parse_report(
    raw: str,
    *,
    reprompt: Callable[[str], Awaitable[str]] | None = None,
) -> ReportPayload:
    parsed = _try_loads(raw)
    if parsed is not None:
        return _validate(parsed)

    if reprompt is None:
        raise LLMParseError(f"无法从 LLM 响应中解析 JSON: {raw[:200]}")

    corrected = await reprompt(_REPROMPT_TEMPLATE.format(original=raw[:500]))
    parsed = _try_loads(corrected)
    if parsed is None:
        raise LLMParseError(f"二次纠正后仍无法解析: {corrected[:200]}")
    return _validate(parsed)
```

**Step 5: 跑测试**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_llm_parser.py -v
```

Expected: 6 passed。

**Step 6: Commit**

```bash
git add backend/app/llm/parser.py backend/tests/unit/test_llm_parser.py backend/tests/fixtures/malformed/
git commit -m "feat: 添加 LLM JSON 解析的 4 级容错策略 + 单元测试"
```

---

## Task 6: `LLMProvider` Protocol + RawLLMResponse [代码]

**Files:**
- Create: `backend/app/llm/base.py`
- Create: `backend/tests/unit/test_provider_contract.py`

**Step 1: 写契约测试**

```python
"""LLMProvider Protocol 的契约测试。
保证未来实现（doubao / deepseek / fake）都符合签名。"""
import pytest
from app.llm.base import LLMProvider, RawLLMResponse


class _DummyProvider:
    name = "dummy"
    model_id = "dummy-1"

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        return RawLLMResponse(
            content='{"x":1}', model="dummy-1", latency_ms=10, provider_payload={}
        )


def test_dummy_satisfies_protocol():
    """Protocol 是 duck-typed，DummyProvider 不继承也应该符合。"""
    p: LLMProvider = _DummyProvider()  # 不抛 = 符合
    assert p.name == "dummy"


async def test_dummy_returns_correct_shape():
    p = _DummyProvider()
    r = await p.analyze(b"fake-image", "fake-prompt")
    assert isinstance(r, RawLLMResponse)
    assert r.content == '{"x":1}'
    assert r.latency_ms >= 0


def test_raw_response_requires_all_fields():
    """RawLLMResponse 所有字段必填，防止后续遗漏。"""
    with pytest.raises(TypeError):
        RawLLMResponse(content="x")  # 缺其他字段
```

**Step 2: 跑看失败**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_provider_contract.py -v
```

Expected: FAIL（`app.llm.base` 不存在）。

**Step 3: 写实现 `backend/app/llm/base.py`**

```python
"""LLMProvider 抽象。
用 Protocol 而不是 ABC，让测试桩 duck-type 通过而不必继承。"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RawLLMResponse:
    content: str
    model: str
    latency_ms: int
    provider_payload: dict


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model_id: str

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse: ...
```

**Step 4: 跑测试**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_provider_contract.py -v
```

Expected: 3 passed。

**Step 5: Commit**

```bash
git add backend/app/llm/base.py backend/tests/unit/test_provider_contract.py
git commit -m "feat: 添加 LLMProvider Protocol + RawLLMResponse"
```

---

## Task 7: Doubao Provider 实现 [代码]

**Files:**
- Create: `backend/app/llm/doubao.py`

**说明**：Doubao 走 OpenAI-compatible 接口（Volcengine Ark），直接用 `openai` SDK 改 `base_url`。**Doubao 实现没有单元测试**（避免打真 LLM）；它的正确性由 Task 9 的 PoC 烟雾测试 + Phase 2 的集成 record-replay 测试覆盖。

**Step 1: 写实现 `backend/app/llm/doubao.py`**

```python
"""Doubao Vision provider，走 Volcengine Ark 的 OpenAI 兼容接口。"""
import base64
import time
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.llm.base import RawLLMResponse


class DoubaoProvider:
    name = "doubao"

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model_id = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"

        t0 = time.monotonic()
        resp: ChatCompletion = await self._client.chat.completions.create(
            model=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.2,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        content = resp.choices[0].message.content or ""
        return RawLLMResponse(
            content=content,
            model=resp.model,
            latency_ms=latency_ms,
            provider_payload=resp.model_dump(),
        )
```

**Step 2: 类型 / lint 检查**

```bash
cd backend && .venv/Scripts/python -m ruff check app/llm/doubao.py
cd backend && .venv/Scripts/python -m mypy app/llm/doubao.py
```

Expected: 都 0 错。

**Step 3: Commit**

```bash
git add backend/app/llm/doubao.py
git commit -m "feat: 添加 Doubao Vision provider 实现（OpenAI 兼容接口）"
```

---

## Task 8: 用户准备 API key 和样图 [用户]

**用户在 chat 里告诉助手"已准备完成"再继续。**

### Step 1: 申请豆包 Vision API key

1. 去 [Volcengine Ark 控制台](https://console.volcengine.com/ark) 注册 / 登录
2. 创建一个 Vision 类的 endpoint（豆包 Vision Pro 系列）
3. 拿到 API key 与 endpoint ID（endpoint ID 就是后面填到 `DOUBAO_MODEL` 的值）

### Step 2: 写本地 `backend/.env`

```
DOUBAO_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=ep-2026xxxxxxxx-xxxxx   # 你创建的 endpoint ID
```

**重要**：`.env` 已被 `.gitignore`，绝不要 commit。

### Step 3: 准备 5 张样图

放到 `backend/tests/fixtures/images/`，命名建议：

```
case_001_scaffold_no_guard.jpg     # 脚手架临边无防护
case_002_no_helmet.jpg             # 未戴安全帽
case_003_exposed_wiring.jpg        # 配电箱 / 线路裸露
case_004_basket_overload.jpg       # 高处堆载 / 物体打击
case_005_fire_extinguisher_missing.jpg  # 消防器材缺失
```

**取材建议**：
- 优先用自己手机拍的真实工地照（最真实，但注意隐私 / 公司 IP）
- 也可以用图库（必应图片搜"建筑施工 隐患"），但要确认许可
- 单张 ≤ 15MB；jpg / png / webp 均可

### Step 4: 决定是否 commit 样图

- 如果是公开图（无隐私）→ commit 进 git（方便复现）
- 如果是涉密的真实工地图 → 加到 `.gitignore` 并自留备份；将 `tests/fixtures/images/.gitkeep` 作为占位

### Step 5: 告诉助手完成

在 chat 中告知"API key 和 5 张图已就位"再继续 Task 9。

---

## Task 9: `poc_doubao.py` 烟雾测试（单图跑通） [混合]

**Files:**
- Create: `backend/scripts/poc_doubao.py`

**Step 1: 写脚本 `backend/scripts/poc_doubao.py`**

```python
"""Phase 1 PoC 入口：单图调豆包 Vision，打印原始响应 + 解析结果。

用法:
    python -m scripts.poc_doubao tests/fixtures/images/case_001_scaffold_no_guard.jpg

环境变量（从 backend/.env 读取）：
    DOUBAO_API_KEY, DOUBAO_BASE_URL, DOUBAO_MODEL
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.llm.doubao import DoubaoProvider
from app.llm.parser import parse_report

# Phase 1 期间，prompt 在脚本里直接调；定稿后迁到 app/llm/prompt.py
PROMPT_V1 = """你是一名资深建筑施工安全工程师。请仔细观察这张工地照片，识别其中的安全隐患。

只返回 JSON 对象，不要附加任何解释、不要用 markdown 代码块包裹。JSON 结构如下：

{
  "inspection_id": "00000000-0000-0000-0000-000000000000",
  "created_at": "2026-01-01T00:00:00Z",
  "plain_warning": "（1-30字口语化警示，任何工地角色秒懂）",
  "summary": "（面向安全员的一句话总结，含整体风险等级）",
  "overall_severity": "high | medium | low",
  "hazards": [
    {
      "category_code": "H1..H10 之一",
      "category_name": "对应中文名",
      "description": "看到的具体现象（专业用语）",
      "severity": "high | medium | low",
      "regulation": "引用规范条款，不确定时留空字符串",
      "suggestion": "可执行的整改建议"
    }
  ],
  "model_meta": {"provider": "doubao", "model": "placeholder", "latency_ms": 0}
}

类别枚举：
H1 高处坠落 | H2 物体打击 | H3 触电 | H4 坍塌 | H5 机械伤害 | H6 火灾 | H7 中毒/窒息 | H8 起重伤害 | H9 个人防护缺失 | H10 其他/文明施工

约束：
- plain_warning 必须口语化、20 字内、任何工地角色（含工人）秒懂
- summary + hazards.description 用专业用语
- regulation 不允许编造，不确定就留空字符串
- 只用简体中文
"""


async def main(image_path: str) -> None:
    load_dotenv()
    api_key = os.environ["DOUBAO_API_KEY"]
    base_url = os.environ["DOUBAO_BASE_URL"]
    model = os.environ["DOUBAO_MODEL"]

    provider = DoubaoProvider(api_key=api_key, base_url=base_url, model=model)
    image_bytes = Path(image_path).read_bytes()
    print(f"→ 调用豆包 ({model})，图片 {len(image_bytes) / 1024:.1f} KB...")

    raw = await provider.analyze(image_bytes, PROMPT_V1)
    print(f"\n=== 原始响应 ({raw.latency_ms} ms) ===\n{raw.content}\n")

    try:
        # reprompt 用同一个 provider 的 analyze，但替换 prompt 为纠正模版
        async def reprompt(corrective_prompt: str) -> str:
            r = await provider.analyze(image_bytes, corrective_prompt)
            return r.content

        report = await parse_report(raw.content, reprompt=reprompt)
    except Exception as e:
        print(f"!!! 解析失败: {e}")
        sys.exit(1)

    print("=== 解析后的报告 ===")
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.poc_doubao <image_path>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
```

**Step 2: 用户跑一次单图烟雾测试**

```bash
cd backend && .venv/Scripts/python -m scripts.poc_doubao tests/fixtures/images/case_001_scaffold_no_guard.jpg
```

Expected:
- 输出"调用豆包..."
- 输出原始响应 + latency
- 输出解析后的报告（JSON）
- exit code 0

**如果失败**：
- 401 → API key 错；检查 `.env`
- 404 model → `DOUBAO_MODEL` 错（应是 endpoint ID 不是 model 名）
- 解析失败 → 把原始响应贴出来给助手，迭代 Prompt
- 其他 → 把完整错误贴出来给助手

**Step 3: Commit 脚本**

```bash
git add backend/scripts/poc_doubao.py
git commit -m "feat: 添加 Phase 1 PoC 单图调用脚本 poc_doubao.py"
```

---

## Task 10: Prompt v1 跑完 5 张图 [混合]

**Files:**
- Create: `docs/specs/prompt-poc-notes.md`

**Step 1: 创建 `docs/specs/prompt-poc-notes.md` 记本**

```markdown
# Phase 1 PoC 迭代记录

> 不是定稿文档。Phase 1 D4 把通过的 Prompt 抄到 app/llm/prompt.py 后，本文保留作决策痕迹。

## v1（2026-05-DD）

**Prompt 摘要**：见 scripts/poc_doubao.py 中 `PROMPT_V1`。

**5 张图结果**：

| 图 | 解析是否通过 | plain_warning 摘要 | 主要识别隐患 | 评判 |
| --- | --- | --- | --- | --- |
| case_001 | | | | |
| case_002 | | | | |
| case_003 | | | | |
| case_004 | | | | |
| case_005 | | | | |

**问题观察**：

- (待填)

**v2 改动方向**：

- (待填)
```

**Step 2: 用户对 5 张图逐张跑**

```bash
for f in tests/fixtures/images/*.jpg; do
  echo "=== $f ==="
  .venv/Scripts/python -m scripts.poc_doubao "$f"
done
```

（PowerShell 版本：`Get-ChildItem tests/fixtures/images/*.jpg | ForEach-Object { ... }`）

**Step 3: 用户填表 + 给出 v2 改动建议**

把结果记到 `prompt-poc-notes.md` 表格里。每行的"评判"用 ✅ / ⚠️ / ❌：
- ✅：报告"看起来像安全员写的"
- ⚠️：方向对但措辞 / 严重度不准
- ❌：识别错 / 漏 / JSON 不合规

**Step 4: Commit 笔记初版**

```bash
git add docs/specs/prompt-poc-notes.md
git commit -m "docs: 添加 Phase 1 Prompt PoC 迭代记录 v1 结果"
```

---

## Task 11: Record-Replay 基础设施 [代码]

**Files:**
- Create: `backend/scripts/replay_capture.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/unit/test_fake_provider.py`

**Step 1: 写 `backend/tests/conftest.py`（含 FakeLLMProvider）**

```python
"""共享测试 fixtures。"""
import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.llm.base import RawLLMResponse


class FixtureMissingError(LookupError):
    pass


class FakeLLMProvider:
    """按 image SHA-256 查 tests/fixtures/llm/ 里的录像返回。"""

    name = "fake"

    def __init__(self, fixture_dir: Path):
        self.model_id = "fake-replay"
        self._by_sha: dict[str, dict] = {}
        for p in fixture_dir.glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            self._by_sha[data["input"]["image_sha256"]] = data["output"]

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        digest = sha256(image_bytes).hexdigest()
        if digest not in self._by_sha:
            raise FixtureMissingError(
                f"未找到 image sha {digest[:12]} 的 LLM 录像。"
                f"跑 python -m scripts.replay_capture 重新录制"
            )
        out = self._by_sha[digest]
        return RawLLMResponse(**out)


@pytest.fixture
def fake_provider(tmp_path) -> FakeLLMProvider:
    """空 fixture 目录的 FakeLLMProvider，单测可手动塞数据。"""
    return FakeLLMProvider(tmp_path)
```

**Step 2: 写测试验证 FakeLLMProvider**

```python
# backend/tests/unit/test_fake_provider.py
"""FakeLLMProvider 行为验证。"""
import json
import pytest
from hashlib import sha256
from tests.conftest import FakeLLMProvider, FixtureMissingError


async def test_replay_returns_recorded_response(tmp_path):
    image = b"fake-image-bytes"
    digest = sha256(image).hexdigest()
    fixture = {
        "input": {"image_sha256": digest, "image_path": "x.jpg", "prompt_version": "v1", "provider": "doubao"},
        "output": {"content": '{"x":1}', "model": "test", "latency_ms": 100, "provider_payload": {}},
    }
    (tmp_path / f"{digest[:8]}.json").write_text(json.dumps(fixture), encoding="utf-8")

    fake = FakeLLMProvider(tmp_path)
    r = await fake.analyze(image, "any prompt")
    assert r.content == '{"x":1}'


async def test_missing_fixture_raises(tmp_path):
    fake = FakeLLMProvider(tmp_path)
    with pytest.raises(FixtureMissingError):
        await fake.analyze(b"never-seen", "any")
```

**Step 3: 跑测试看通过**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_fake_provider.py -v
```

Expected: 2 passed。

**Step 4: 写 `backend/scripts/replay_capture.py`**

```python
"""录制 LLM 响应到 tests/fixtures/llm/，供集成测试重放。

用法：
    python -m scripts.replay_capture --prompt-version v2
"""
import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

from app.llm.doubao import DoubaoProvider
from scripts.poc_doubao import PROMPT_V1  # Phase 1 期间 prompt 在脚本里

IMAGES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "llm"


async def main(prompt_version: str) -> None:
    load_dotenv()
    provider = DoubaoProvider(
        api_key=os.environ["DOUBAO_API_KEY"],
        base_url=os.environ["DOUBAO_BASE_URL"],
        model=os.environ["DOUBAO_MODEL"],
    )
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    for image_path in sorted(IMAGES_DIR.glob("*.jpg")):
        image = image_path.read_bytes()
        digest = sha256(image).hexdigest()
        print(f"→ 录制 {image_path.name}（{len(image)/1024:.1f} KB, sha {digest[:8]}）")

        raw = await provider.analyze(image, PROMPT_V1)
        out_path = FIXTURES_DIR / f"{image_path.stem}.json"
        out_path.write_text(json.dumps({
            "input": {
                "image_sha256": digest,
                "image_path": str(image_path.relative_to(Path.cwd())),
                "prompt_version": prompt_version,
                "provider": "doubao",
            },
            "output": {
                "content": raw.content,
                "model": raw.model,
                "latency_ms": raw.latency_ms,
                "provider_payload": raw.provider_payload,
            },
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "captured_by": "scripts/replay_capture.py",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   ✓ 写入 {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-version", default="v1")
    args = parser.parse_args()
    asyncio.run(main(args.prompt_version))
```

**Step 5: Commit 基础设施**

```bash
git add backend/tests/conftest.py backend/tests/unit/test_fake_provider.py backend/scripts/replay_capture.py
git commit -m "feat: 添加 FakeLLMProvider + replay_capture 录像基础设施"
```

**Step 6: 用户跑首次录制**

```bash
cd backend && .venv/Scripts/python -m scripts.replay_capture --prompt-version v1
```

Expected: 5 个 `tests/fixtures/llm/case_*.json` 写入完成。

**Step 7: 决定是否 commit 录像**

录像 JSON 含 LLM 原始响应（可能包含模型分析中文文本）。建议 commit（小，方便集成测试），但若涉及敏感内容用户决定。

```bash
git add backend/tests/fixtures/llm/
git commit -m "test: 录制 Prompt v1 在 5 张样图上的 LLM 响应"
```

---

## Task 12: 迭代 Prompt 到 v2/v3 [用户为主]

**Files:**
- Modify: `backend/scripts/poc_doubao.py`（更新 PROMPT_V1 → PROMPT_V2 → PROMPT_V3）
- Modify: `docs/specs/prompt-poc-notes.md`（追加 v2 / v3 节）

**Step 1: 基于 v1 结果改 Prompt**

常见改动方向：
- 描述类别更清楚（"高处坠落 = 2 米以上无防护的工作面"）
- 强化"不允许编造规范条款"
- 加 few-shot 例子（给 1 个标准报告示范）
- 调整 plain_warning 的字数 / 措辞要求

**Step 2: 每改一版**

- 把新 prompt 替换到 `poc_doubao.py` 的 `PROMPT_V1` 常量（变量名可仍叫 `PROMPT_V1`，反正脚本只看这一个）
- 跑 `replay_capture.py --prompt-version v2`（覆盖 fixtures，旧版本如需保留可手动改文件名）
- 跑所有 5 张图、记结果到 `prompt-poc-notes.md`

**Step 3: 退出条件**

至少 3/5 张图人工评判"看起来像安全员写的"（✅）。达不到 → 继续迭代或考虑切 DeepSeek。

**Step 4: Commit 迭代过程**

```bash
git add backend/scripts/poc_doubao.py docs/specs/prompt-poc-notes.md backend/tests/fixtures/llm/
git commit -m "feat: Prompt 迭代到 v2/v3，达到 3/5 通过门槛"
```

（commit 频次按你自己节奏，每个有意义的版本一次即可。）

---

## Task 13: 压缩对比实验 [用户]

**Files:**
- Create: `backend/scripts/poc_compression_ab.py`
- Modify: `docs/specs/prompt-poc-notes.md`（追加"§ 压缩 A/B"节）

**Step 1: 写脚本 `backend/scripts/poc_compression_ab.py`**

```python
"""对每张样图跑「原图」+「压到长边 1280」两次，对比 LLM 输出。"""
import asyncio
import json
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image  # 临时实验依赖，跑完可以不留

from app.llm.doubao import DoubaoProvider
from scripts.poc_doubao import PROMPT_V1

IMAGES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"


def compress(image_bytes: bytes, long_side: int = 1280) -> bytes:
    im = Image.open(BytesIO(image_bytes))
    w, h = im.size
    if max(w, h) <= long_side:
        return image_bytes
    ratio = long_side / max(w, h)
    im2 = im.resize((int(w * ratio), int(h * ratio)))
    buf = BytesIO()
    im2.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def main():
    load_dotenv()
    provider = DoubaoProvider(
        api_key=os.environ["DOUBAO_API_KEY"],
        base_url=os.environ["DOUBAO_BASE_URL"],
        model=os.environ["DOUBAO_MODEL"],
    )

    for image_path in sorted(IMAGES_DIR.glob("*.jpg")):
        original = image_path.read_bytes()
        compressed = compress(original)
        print(f"\n=== {image_path.name} ===")
        print(f"原图 {len(original)/1024:.0f} KB → 压缩 {len(compressed)/1024:.0f} KB")

        r_orig = await provider.analyze(original, PROMPT_V1)
        r_comp = await provider.analyze(compressed, PROMPT_V1)

        print(f"\n--- 原图响应 ({r_orig.latency_ms} ms) ---\n{r_orig.content[:500]}")
        print(f"\n--- 压缩响应 ({r_comp.latency_ms} ms) ---\n{r_comp.content[:500]}")


if __name__ == "__main__":
    asyncio.run(main())
```

需要补一个依赖：`uv pip install pillow`。

**Step 2: 跑实验**

```bash
cd backend && .venv/Scripts/python -m scripts.poc_compression_ab
```

**Step 3: 用户人工判断 + 写结论**

在 `prompt-poc-notes.md` 追加：

```markdown
## § 压缩 A/B 实验（2026-05-DD）

**方法**：5 张图各跑「原图」+「软压到长边 1280」，对比 LLM 输出的隐患识别完整度。

**结果**：

| 图 | 原图识别项 | 压缩识别项 | 差异 |
| --- | --- | --- | --- |
| case_001 | | | |
| case_002 | | | |
| case_003 | | | |
| case_004 | | | |
| case_005 | | | |

**结论**：（任选其一并记入）
- 无显著差异 → v0.2 可加回压缩以省 token
- 压缩明显劣化（如丢小目标 / 文字识别变差） → 永久保持原图直传
```

**Step 4: Commit**

```bash
git add backend/scripts/poc_compression_ab.py docs/specs/prompt-poc-notes.md
git commit -m "test: 压缩 A/B 实验脚本 + 结论"
```

---

## Task 14: Freeze Prompt 到 `app/llm/prompt.py` [代码]

**Files:**
- Create: `backend/app/llm/prompt.py`
- Create: `backend/tests/unit/test_prompt.py`
- Modify: `backend/scripts/poc_doubao.py`（改成 import）
- Create: `docs/specs/prompt.md`（用户写正式文档）

**Step 1: 写 `backend/app/llm/prompt.py`**

把 Phase 1 最后通过的 Prompt 从 `poc_doubao.py` 搬过来：

```python
"""定稿的 LLM Prompt 模版（Phase 1 PoC 出炉）。

修改前请同步更新 docs/specs/prompt.md 和 prompt-poc-notes.md（保留决策痕迹）。"""

PROMPT_VERSION = "v3"  # 与 prompt-poc-notes.md 对应

ANALYZE_PROMPT = """..."""  # 把 PROMPT_V1 内容 paste 过来（实际是最后通过的版本）

REPROMPT_TEMPLATE = (
    "你上一次的输出不是合法的 JSON 对象。请只输出符合规定格式的 JSON 对象，"
    "不要附加任何说明、不要用 markdown 代码块包裹。原响应：\n{original}"
)
```

**Step 2: 写最低限度的"prompt 不为空 + 含关键字段"测试**

```python
# backend/tests/unit/test_prompt.py
"""Prompt 内容的最小约束测试，防止误删 / 误改。"""
from app.llm.prompt import ANALYZE_PROMPT, PROMPT_VERSION


def test_prompt_not_empty():
    assert len(ANALYZE_PROMPT) > 100


def test_prompt_enumerates_all_categories():
    """H1-H10 必须全部在 prompt 里被枚举到。"""
    for code in [f"H{i}" for i in range(1, 11)]:
        assert code in ANALYZE_PROMPT, f"prompt 缺少 {code}"


def test_prompt_enforces_json_only():
    assert "JSON" in ANALYZE_PROMPT
    assert "代码块" in ANALYZE_PROMPT or "markdown" in ANALYZE_PROMPT.lower()


def test_prompt_forbids_fabrication():
    """必须有"不允许编造"之类的约束。"""
    assert "不允许" in ANALYZE_PROMPT or "不要编造" in ANALYZE_PROMPT or "留空" in ANALYZE_PROMPT


def test_prompt_version_set():
    assert PROMPT_VERSION  # 非空字符串
```

**Step 3: 跑测试**

```bash
cd backend && .venv/Scripts/python -m pytest tests/unit/test_prompt.py -v
```

Expected: 5 passed。

**Step 4: 改 `poc_doubao.py` 引用统一来源**

```python
# 删除文件里的 PROMPT_V1 常量定义，改成：
from app.llm.prompt import ANALYZE_PROMPT
# 把所有 PROMPT_V1 用法替换成 ANALYZE_PROMPT
```

同样改 `replay_capture.py` 和 `poc_compression_ab.py`。

**Step 5: 用户写 `docs/specs/prompt.md` 正式文档**

按架构 design §5 的描述写：
- System Prompt 全文
- User Prompt 拼装规则
- 输出 schema 重申
- 4 级容错策略说明
- 与 `prompt-poc-notes.md` 的关系（前者是最终契约，后者是决策痕迹）

**Step 6: Commit**

```bash
git add backend/app/llm/prompt.py backend/tests/unit/test_prompt.py backend/scripts/ docs/specs/prompt.md
git commit -m "feat: Freeze Phase 1 Prompt 到 app/llm/prompt.py + 落定稿文档"
```

---

## Task 15: Phase 1 退出门验证 [混合]

**Files:** 无修改，只检查。

**Step 1: 单元测试全跑**

```bash
cd backend && .venv/Scripts/python -m pytest -v
```

Expected: 全 passed，**0 failed**，**0 skipped**。如有 skipped → 回去补、不允许带 skip 过门。

**Step 2: 静态检查**

```bash
cd backend && .venv/Scripts/python -m ruff check .
cd backend && .venv/Scripts/python -m mypy app/
```

Expected: 0 错。

**Step 3: 人工评判结果汇总**

确认 `docs/specs/prompt-poc-notes.md` 表格里 5 张图至少 3 张 ✅。

**Step 4: 决策点**

- 3+ 张通过 → **Phase 1 PASS**，可进入 Phase 2（届时启动新一轮 brainstorming + writing-plans）
- < 3 张通过 → 决策：
  - 继续迭代 Prompt（回 Task 12）
  - 切 DeepSeek 重跑（实现 `app/llm/deepseek.py`，重跑 Task 9-12）
  - 用更接近实际场景的样图（回 Task 8）

**Step 5: 总结 commit**

把 Phase 1 的总结追加到 `prompt-poc-notes.md` 末尾：

```markdown
## § Phase 1 总结（2026-05-DD）

- 通过率：N / 5
- 最终 Prompt 版本：v3
- LLM 选型：✅ 豆包 / ❌ 切 DeepSeek
- 压缩策略：✅ 保持原图 / 可加回压缩
- 已知问题（带入 Phase 2）：
  - ...
```

```bash
git add docs/specs/prompt-poc-notes.md
git commit -m "docs: Phase 1 退出门总结"
```

---

## Phase 1 完成标准

- ✅ 15 个 task 全完成（部分由用户执行）
- ✅ `pytest backend/` → 0 failed / 0 skipped
- ✅ `ruff check` / `mypy app/` → 0 错
- ✅ 5 张样图中 ≥ 3 张人工评判通过
- ✅ Prompt 定稿到 `app/llm/prompt.py` + `docs/specs/prompt.md`
- ✅ Record-replay fixtures 录好（Phase 2 集成测试就靠它们）
- ✅ 压缩 A/B 实验结论写入 `prompt-poc-notes.md`

## Phase 1 不在本计划内的事

- FastAPI 路由 / SQLite 存储 / 后台任务 / 错误中间件（Phase 2）
- 完整 `app/config.py` pydantic-settings（脚本暂用 `os.environ`，Phase 2 切换）
- 图片校验 service（Phase 2，因为它服务于 HTTP 入参）
- DeepSeek provider 实现（Phase 2 D9 stub；Phase 1 只有豆包不够用时才提前实现）
- 任何前端代码（Phase 3）

## 风险与回退

| 风险 | 触发 | 回退 |
| --- | --- | --- |
| Doubao API 调不通（网络 / 鉴权） | Task 9 失败 | 切 OpenAI / DeepSeek 跑 PoC；架构层不变 |
| Prompt 调不出可用输出 | Task 12 迭代 5 次仍 < 3/5 | 切 DeepSeek 重跑 Task 9-12 |
| 5 张样图代表性不够 | Task 15 通过但实际效果差 | 补样图，回 Task 10 |
| 压缩实验显示劣化严重 | Task 13 | 记入"永久不压缩"决策，无回退动作 |
