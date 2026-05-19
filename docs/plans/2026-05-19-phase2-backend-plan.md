# Phase 2 · Backend Skeleton Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 [`docs/plans/2026-05-18-架构-design.md`](./2026-05-18-架构-design.md) §2 设计的"后端 FastAPI 骨架"实施落地 — `POST /api/v1/inspections` 异步上传图片 → `GET /api/v1/inspections/{id}` 轮询状态 → 拿到 Phase 1 已冻结的 Prompt v1（或 v2）输出的结构化 ReportPayload。

**Upstream specs:**
- [`docs/plans/2026-05-18-架构-design.md`](./2026-05-18-架构-design.md) §2 — 后端目录、接口签名、DI、错误处理、数据流（**本文不重复，task 描述里直接引 §x.y**）
- [`docs/specs/report-schema.md`](../specs/report-schema.md) — 报告 JSON 契约（Phase 1 已实现 Pydantic ReportPayload）
- [`docs/specs/prompt-poc-notes.md`](../specs/prompt-poc-notes.md) — Phase 1 Prompt v1 决策痕迹 + 带入 Phase 2 的 4 个已知问题

**Tech stack (Phase 1 之上的增量):**
- FastAPI + `pydantic-settings` + `slowapi`（速率限制）
- stdlib `sqlite3`（per-request connection；不引 ORM）
- stdlib `logging`（自定义 JSON formatter）
- pytest + `fastapi.testclient.TestClient`（集成测试）

**Phase 1 已就位（本 phase 不动）:**
- `app/llm/{base, claude_cli, parser, prompt}.py`、`app/schemas/report.py`、`app/errors.py`
- `tests/conftest.py` 的 FakeLLMProvider、5 张样图 + 录像
- 单元测试 42/0/0 已通过

---

## 重要前置说明

**本计划全部为"代码任务"**：Phase 1 末尾用户已经做了所有"用户参与"决策；Phase 2 不需要用户提供凭证或数据，只在 **T9（Prompt v2 重录 fixtures）** 时会跑真 LLM ~$1。

**测试硬规则**（[[feedback-phase-unit-tests]]）：phase 退出时 `pytest backend/` 必须 **0 failed / 0 skipped**。任何"先 skip 等会儿补"的诱惑直接驳回。

---

## Phase 2 brainstorm 决策（2026-05-19）

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 分支策略 | 一口气走完，单 PR | 个人项目；Phase 2 是完整骨架、拆没必要 |
| 子进程并发上限 | 信号量 = 2 | 单人使用场景 2 个并发足够；峰值 ~200MB RSS 可控 |
| 图片存储 | 本地 FS 只主（`uploads/{uuid}.{ext}`），**不抽象** OSS 接口 | MVP YAGNI；微信小程序场景不需要 CDN |
| 速率限制 | `slowapi` | 标准库、decorator 风格、默认 429 响应 |
| 日志 | stdlib `logging` + JSON formatter | 每请求记 `inspection_id / latency_ms / cost_usd / model / error_code` |
| Phase 2 退出门 | 单元 0/0/0 + 集成 happy + failure 双通过 + Prompt v2 ≥3/5 + ruff/mypy clean | 见 T10 |
| Phase 1 follow-ups 处理 | **全部** 4 项在 Phase 2 内闭环 | 见下方 |

**Phase 1 带入的 4 个 follow-ups（融入对应 task）：**
1. `--model sonnet` alias 固定为全名 → **T1**（Config + .env.example）
2. Prompt v2 补三个约束（同类合并 / plain_warning 对齐 / model_meta 说明） → **T9**
3. 子进程部署耦合需文档化 → **T9 末尾** README/deploy 一节
4. 60-260s 延迟 → `backend_hard_timeout_s` 调到 300 → **T1**

---

## 任务依赖图

```
T1 Config ──┐
            ├─> T2 Storage ──┐
            │                 │
            ├─> T3 Image svc ─┤
            │                 │
            │                 ├─> T4 Inspection svc + Runner ──┐
            │                 │                                 │
            │                 │                                 ├─> T5 Routes + DI ──┐
            │                 │                                 │                    │
            │                 │                                 │                    ├─> T6 Cross-cut（exc handler / logging / orphan）──┐
            │                 │                                 │                    │                                                    │
            │                 │                                 │                    │                                                    ├─> T7 Rate limit ──> T8 集成测试
            │                 │                                 │                    │                                                    │
            └─────────────────┴─────────────────────────────────┴────────────────────┴────────────────────────────────────────────────────┘

T9 Prompt v2 + 重录 fixtures（与 T1-T8 独立，可并行或最后做）
                                       │
                                       ▼
                              T10 Phase 2 退出门验证
```

---

## Task 1: Config + 环境变量 + Phase 1 follow-ups [代码]

**Files:**
- Create: `backend/app/config.py`
- Modify: `backend/.env.example`
- Create: `backend/tests/unit/test_config.py`

**架构参考：** §2.3 `Settings` 类

**Approach:**
1. `Settings(BaseSettings)`：字段名严格对齐 §2.3 + 4 个 Phase 1 follow-ups
   - `claude_model: str = "claude-sonnet-4-5"`（**全名，不用 sonnet alias** — 实测 alias 会 fallback 到 Opus）
   - `claude_timeout_seconds: int = 300`（从 180 调上来；Phase 1 实测 case_004 跑了 266s）
   - `backend_hard_timeout_s: int = 320`（> claude_timeout_seconds，给 stdlib timeout 余地）
   - `timeout_ms: int = 330000`（前端轮询 > backend hard timeout）
   - 其余字段 sqlite_path / upload_dir / max_image_mb / poll_interval_ms / rate_limit_per_minute 照 §2.3
2. `get_settings()` 用 `@lru_cache` 单例
3. `.env.example` 更新到与 Settings 默认值一致（含注释解释 alias 不稳）

**Tests:**
- `test_settings_loads_defaults`：无 env vars 时所有默认值符合预期
- `test_settings_env_override`：`monkeypatch.setenv` 后值被覆盖
- `test_get_settings_is_cached`：两次调用拿到同一实例

**Validation:** `pytest tests/unit/test_config.py -v` → 3 passed；ruff + mypy clean。

**Commit:**
```
feat: Task 1 — Settings (pydantic-settings) + Phase 1 follow-ups

- 新增 backend/app/config.py：Settings + get_settings (@lru_cache)
- 固定 CLAUDE_MODEL=claude-sonnet-4-5 全名（解决 Phase 1 alias 路由问题）
- CLAUDE_TIMEOUT_SECONDS 180 → 300、backend_hard_timeout_s 150 → 320
- 同步更新 .env.example
- 3 个 Settings 单元测试
```

---

## Task 2: Storage 层（SQLite + InspectionRepo）[代码]

**Files:**
- Create: `backend/app/storage/__init__.py`、`db.py`、`inspection_repo.py`
- Create: `backend/tests/unit/test_inspection_repo.py`

**架构参考：** §2.1 storage 目录、§2.2 `InspectionRepo` 接口

**Approach:**
1. `db.py`：
   - `init_schema(conn)`：建 `inspections` 表（id / status / image_path / created_at / updated_at / report_json / error_json / model_meta_json）
   - `connect(path)`：`sqlite3.connect` + `row_factory = sqlite3.Row`
   - 启用 WAL 模式（多 reader / 单 writer 并发友好）
2. `inspection_repo.py`：纯函数 + 第一参 `conn`
   - `create(conn, image_path) -> str(uuid)`
   - `get(conn, id) -> InspectionRow | None`
   - `update_processing(conn, id)`、`update_succeeded(conn, id, report, meta)`、`update_failed(conn, id, error_payload)`
   - `list_orphaned_queued(conn) -> list[InspectionRow]`（启动恢复用）
   - `gc_older_than(conn, days=7) -> int`
3. `InspectionRow` 用 `@dataclass`（不引 SQLModel）

**Tests:**（pytest fixture：每个测试一个 tmp sqlite 文件）
- `test_create_and_get`：写完能读出来、status=queued、id 是合法 uuid
- `test_status_transitions`：queued → processing → succeeded（顺序约束不在 repo 层；只测能转）
- `test_update_succeeded_persists_report`：报告 JSON 完整存得回来
- `test_update_failed_persists_error`：错误 JSON 同上
- `test_list_orphaned_queued`：写 3 条不同状态，只回 queued 那条
- `test_gc_older_than`：写 2 条 8 天前 + 1 条今天，GC 后剩 1 条
- `test_get_missing_returns_none`：不存在的 id 返 None

**Validation:** ~7 个测试全 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 2 — SQLite storage 层（db + InspectionRepo）

- backend/app/storage/db.py：init_schema + connect + WAL 模式
- backend/app/storage/inspection_repo.py：CRUD + GC + 孤儿查询纯函数
- 7 个 repo 单元测试（每测一个 tmp sqlite 文件）
```

---

## Task 3: Image service（校验 + 落盘）[代码]

**Files:**
- Create: `backend/app/services/__init__.py`、`image.py`
- Create: `backend/tests/unit/test_image_service.py`

**架构参考：** §2.1 services 目录、§4.4 图片传输约定

**Approach:**
1. `image.py`：
   - `ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}`
   - `validate(content_type, size_bytes) -> None`：超 MIME 抛 `InvalidImageError`；超 `max_image_mb` 抛 `ImageTooLargeError`（**新增**：在 `app/errors.py` 加一个，对齐 §2.4）
   - `save(image_bytes, upload_dir, ext) -> Path`：写 `{uuid4()}.{ext}`，返回绝对路径
2. **不压缩 / 不缩放**（架构 §4.4 + Phase 1 已决定）

**Tests:**
- `test_validate_accepts_jpeg / png / webp`
- `test_validate_rejects_pdf`：抛 `InvalidImageError`
- `test_validate_rejects_oversize`：>15MB 抛 `ImageTooLargeError`
- `test_save_writes_file_and_returns_path`：bytes 写进 `tmp_path`、文件存在
- `test_save_filename_is_uuid_ext`：返回的路径 stem 是合法 uuid

**Add to errors.py:** `ImageTooLargeError(http_status=413)` + 2 个 test。

**Validation:** ~5 + 2 个测试全 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 3 — Image service（校验 + 落盘）+ ImageTooLargeError

- backend/app/services/image.py：MIME / size 校验 + uuid 命名落盘
- backend/app/errors.py：新增 ImageTooLargeError (413)
- 5 个 image_service 测试 + 2 个 errors 测试
```

---

## Task 4: Inspection service + 后台 runner [代码]

**Files:**
- Create: `backend/app/services/inspection.py`
- Create: `backend/app/tasks/__init__.py`、`inspection_runner.py`
- Create: `backend/tests/unit/test_inspection_service.py`
- Create: `backend/tests/unit/test_inspection_runner.py`

**架构参考：** §2.2 `run_inspection`、§2.5 数据流

**Approach:**
1. `services/inspection.py`：
   - 函数 `run_inspection(inspection_id, image_bytes, provider, repo, conn)`
   - 状态机：mark processing → `provider.analyze` → `parse_report` → mark succeeded（含 model_meta）
   - 用 `asyncio.Semaphore(2)`（**或全局单例**）限制同时调 provider 的数量；信号量在模块级实例化（单进程多请求够用，Phase 3 上多进程时再说）
   - 任何异常 → mark failed（带 `error_payload`，从异常 `code/user_message` 抽）
2. `tasks/inspection_runner.py`：FastAPI `BackgroundTasks` 调用的 entry point；从依赖工厂拿 connection / repo / provider，调 `run_inspection`，**自己管 connection 生命周期**（async with 或显式 close）

**Tests:**
- inspection_service：
  - `test_run_inspection_happy_path`：mock provider + repo，状态 queued → processing → succeeded
  - `test_run_inspection_llm_parse_error`：provider 返垃圾 → LLMParseError → 状态 failed + error_payload
  - `test_run_inspection_llm_timeout`：mock 抛 LLMTimeoutError → 状态 failed
  - `test_semaphore_caps_concurrent`：起 5 个并发，验证最多 2 个同时进入 analyze 阶段
- inspection_runner：
  - `test_runner_invokes_service_and_closes_conn`：mock service，验证 conn.close() 被调

**Validation:** ~5 个测试全 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 4 — Inspection service + 后台 runner（含信号量=2）

- backend/app/services/inspection.py：状态机编排 + asyncio.Semaphore(2)
- backend/app/tasks/inspection_runner.py：BackgroundTasks 入口
- 5 个测试覆盖 happy / parse_error / timeout / 信号量
```

---

## Task 5: Routes + Dependencies [代码]

**Files:**
- Create: `backend/app/dependencies.py`
- Create: `backend/app/routes/__init__.py`、`inspections.py`、`health.py`
- Create: `backend/app/schemas/inspection.py`（API 请求 / 响应壳）
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_routes.py`

**架构参考：** §2.1 routes、§2.3 dependencies

**Approach:**
1. `dependencies.py`：
   - `get_db()`：per-request `sqlite3.Connection`，`yield` + `finally close`
   - `get_repo(conn)`：薄包装 InspectionRepo 模块函数
   - `get_llm_provider(settings)`：根据 settings 实例化 ClaudeCLIProvider 单例（用 `@lru_cache`，由 settings 哈希）
2. `schemas/inspection.py`：
   - `CreateInspectionResponse`：`inspection_id / poll_url / poll_interval_ms / timeout_ms / status="queued"`
   - `GetInspectionResponse`：`inspection_id / status / report? / error? / created_at / updated_at`
3. `routes/inspections.py`：
   - `POST /api/v1/inspections`：接 multipart `image: UploadFile`、调 image_service.validate + save、repo.create、`background_tasks.add_task(inspection_runner.run, ...)`、返 202 + CreateInspectionResponse
   - `GET /api/v1/inspections/{id}`：调 repo.get、返 GetInspectionResponse 或 404
4. `routes/health.py`：`GET /api/v1/healthz` 返 `{"status": "ok"}`（浅探测，不验下游）

**Tests:**（用 `TestClient` + `dependency_overrides`）
- `test_post_inspection_returns_202_and_poll_info`
- `test_post_inspection_rejects_invalid_mime`：返 400
- `test_post_inspection_rejects_oversize`：返 413
- `test_get_inspection_returns_queued_immediately`：POST 后立刻 GET，状态 queued
- `test_get_inspection_404`：随机 uuid 返 404
- `test_healthz`：返 200 + ok

**Validation:** 6 个集成测试 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 5 — FastAPI routes + dependencies + Inspection API schemas

- backend/app/dependencies.py：DI 工厂（db / repo / llm provider）
- backend/app/routes/{inspections, health}.py：POST/GET inspections + healthz
- backend/app/schemas/inspection.py：API 请求/响应壳
- 6 个 TestClient 集成测试
```

---

## Task 6: 跨切关注点（全局异常 handler + structured logging + 启动孤儿恢复）[代码]

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/logging_config.py`
- Create: `backend/tests/unit/test_logging_config.py`
- Create: `backend/tests/integration/test_lifecycle.py`

**架构参考：** §2.4 错误处理、§2.6 启动期孤儿恢复

**Approach:**
1. `logging_config.py`：
   - `JsonFormatter(logging.Formatter)`：把 LogRecord 转 JSON，每行一个事件
   - 字段：`timestamp / level / logger / message / inspection_id / latency_ms / cost_usd / model / error_code`（后 5 项从 `extra={}` 透传）
   - `setup_logging(level="INFO")`：清空 root handlers、装 JSON formatter 到 stdout
2. `main.py`：
   - `app = FastAPI(...)`
   - 启动时 `setup_logging()` + `init_schema()` + 孤儿恢复（§2.6 策略：把 `queued` 全部标 failed，附 `code=INTERNAL`、`user_message="服务重启导致任务中断，请重试"`）
   - `@app.exception_handler(SafetyScoutError)` 全局映射到 `{"error": {"code", "message", "user_message"}}` + HTTP code
   - 挂 routes

**Tests:**
- logging_config：
  - `test_json_formatter_outputs_valid_json`：跑一条 log，capsys 抓 stdout，json.loads 通过
  - `test_extra_fields_propagated`：log 带 `extra={"inspection_id": "..."}`，JSON 含该字段
- lifecycle 集成：
  - `test_startup_marks_orphans_failed`：预先往 tmp DB 写 1 条 queued，启动 FastAPI app，验证状态变 failed
  - `test_global_handler_maps_invalid_image_error`：注入路由抛 InvalidImageError，HTTP 返 400 + 标准 error 包

**Validation:** ~4 个测试 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 6 — 全局异常 handler + structured JSON logging + 启动孤儿恢复

- backend/app/main.py：FastAPI 入口 + lifespan + exception handler
- backend/app/logging_config.py：JsonFormatter（每行 JSON 事件）
- 启动期把 queued 孤儿标 failed（不重跑，§2.6 策略）
- 4 个测试覆盖 logging 格式 / 孤儿恢复 / 异常映射
```

---

## Task 7: Rate limit（slowapi）[代码]

**Files:**
- Modify: `backend/pyproject.toml`（加 `slowapi>=0.1.9`）
- Modify: `backend/app/main.py`（挂 limiter middleware）
- Modify: `backend/app/routes/inspections.py`（POST 加 `@limiter.limit("10/minute")`）
- Create: `backend/tests/integration/test_rate_limit.py`

**架构参考：** §2.3 `rate_limit_per_minute = 10`

**Approach:**
1. `slowapi.Limiter(key_func=get_remote_address)` 实例化、挂 `app.state.limiter`
2. 注册 `_rate_limit_exceeded_handler` 把 429 包成标准 error 形态（与 SafetyScoutError 一致）
3. POST `/api/v1/inspections` decorator `@limiter.limit("10/minute")`

**Tests:**
- `test_eleventh_request_in_a_minute_returns_429`：发 10 个 POST 都 202、第 11 个 429
- `test_get_endpoint_not_rate_limited`：GET 20 次都成功
- `test_rate_limit_response_shape`：429 响应体含 `error.code="RATE_LIMITED"` + `user_message` 中文

**Validation:** 3 个测试 pass；ruff + mypy clean。

**Commit:**
```
feat: Task 7 — slowapi 速率限制（10/min POST，per-IP）

- 加 slowapi 依赖
- POST /api/v1/inspections @limiter.limit("10/minute")
- 429 响应统一为 SafetyScoutError 错误包格式
- 3 个集成测试
```

---

## Task 8: 集成测试（happy + failure）[代码]

**Files:**
- Create: `backend/tests/integration/test_inspection_happy.py`
- Create: `backend/tests/integration/test_inspection_failure.py`

**架构参考：** §5.3 集成测试清单

**Approach:**（核心：FakeLLMProvider 走 record-replay）
1. happy path：
   - 用 `TestClient` 把 `app.dependency_overrides[get_llm_provider]` 换成 FakeLLMProvider(fixtures/llm/)
   - POST `tests/fixtures/images/case_001_*.jpg`
   - 短轮询 GET 直到 status != queued/processing
   - 断言 status=succeeded、report 含 ≥1 hazard、overall_severity 合法
2. failure path：
   - FakeLLMProvider 注入返回"垃圾文本"的 stub
   - POST 任意图、轮询直到 status=failed
   - 断言 error.code=LLM_PARSE_FAILED、user_message 非空

**Tests:** 上述 2 个 + 1 个轮询超时测试（FakeLLMProvider 故意延迟，验证客户端能识别 timeout）。

**Validation:** 3 个集成测试 pass；**累计 happy + failure 全通 → Phase 2 退出门主条件达成**。

**Commit:**
```
test: Task 8 — 集成测试 happy + failure 双通路 + 超时

- POST → 轮询 GET → succeeded 端到端（FakeLLMProvider 注入 case_001 fixture）
- POST → LLMParseError → failed + error_payload
- 客户端轮询超时识别
- Phase 2 退出门主条件达成
```

---

## Task 9: Prompt v2 迭代 + 重录 fixtures + 部署文档 [混合]

**Files:**
- Modify: `backend/app/llm/prompt.py`（v1 → v2）
- Modify: `docs/specs/prompt-poc-notes.md`（追加 v2 节）
- Re-generate: `backend/tests/fixtures/llm/case_*.json`（跑 `replay_capture.py`）
- Modify: `README.md`（新增"部署"一节）

**Approach:**
1. Prompt v2 改动（来自 Phase 1 v2 改动方向）：
   - 加 "同一 category_code 下的多条隐患应合并为单条 hazard，description 用分号串接现象"
   - 加 "plain_warning 必须呼应 hazards[0] 的核心风险；hazards 按结构性 / 不可逆程度排序"
   - 加 "model_meta 字段值随便填，由后端覆盖"
   - `PROMPT_VERSION = "v2"`
2. 跑 `cd backend && .venv/Scripts/python -m scripts.replay_capture --prompt-version v2`（**会真打 LLM，~$1**）
3. 5 张图过 `poc_claude.py` 重做评判表，**目标 ≥3/5 ✅**（v1 已 4/5；v2 应至少持平）
4. 用户人工评判后追加到 prompt-poc-notes.md
5. README.md 新增 "## 部署"：明确"backend 运行的机器必须装 claude CLI 且已 OAuth 登录；docker 化或迁机器请重新登录"
6. 跑 `pytest backend/tests/integration/` 确保新 fixtures 仍走通集成测试

**Validation:**
- replay_capture 退出 0、5 个 fixture 文件刷新
- 人工评判表 ≥3/5 ✅
- 集成测试仍 pass（fixtures 内容变了，但 schema 不变）

**Commit:**
```
feat: Task 9 — Prompt v2 + 重录 fixtures + 部署文档

- prompt.py：v1 → v2（同类合并 / plain_warning 对齐 / model_meta 说明）
- 5 张样图 fixtures 重录（跑 replay_capture, 真 LLM ~$1）
- prompt-poc-notes.md 追加 v2 实测节
- README.md 新增"部署"节：claude CLI + OAuth 登录硬依赖文档化
```

---

## Task 10: Phase 2 退出门验证 [验证]

**Files:** 无修改，只检查。

**Step 1: 单元 + 集成测试全跑**
```bash
cd backend && .venv/Scripts/python -m pytest -v
```
Expected: 全 passed、**0 failed**、**0 skipped**。

**Step 2: 静态检查**
```bash
cd backend && .venv/Scripts/python -m ruff check .
cd backend && .venv/Scripts/python -m mypy app/ scripts/ tests/conftest.py
```
Expected: 0 错。

**Step 3: 本地手工跑一次端到端**（不强制但推荐）
```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
# 另一窗口：
curl -X POST -F "image=@tests/fixtures/images/case_001_stepladder_over_2_meters.jpg" \
  http://127.0.0.1:8000/api/v1/inspections
# 拿到 inspection_id 后：
curl http://127.0.0.1:8000/api/v1/inspections/{id}
# 轮询直到 status=succeeded（~90s）
```
Expected: 拿到完整 ReportPayload。

**Step 4: 总结追加到 prompt-poc-notes.md**
```markdown
## § Phase 2 退出门总结（2026-05-DD）

- 单元 + 集成测试 N passed / 0 failed / 0 skipped
- Prompt v2 评判：M/5 ✅
- 端到端手工验证：✅
- 累计 commit：N 个
- 带入 Phase 3 的已知问题：……
```

**Step 5: PR**
```bash
git push -u origin feat/phase-2-backend
gh pr create --title "Phase 2 Backend: FastAPI 骨架 + 集成测试 + Prompt v2" --body ...
```

---

## Phase 2 完成标准

- ✅ 10 个 task 全完成
- ✅ `pytest backend/` → 0 failed / 0 skipped（单元 + 集成）
- ✅ `ruff check` / `mypy app/` → 0 错
- ✅ 集成测试 happy + failure 双通路 pass
- ✅ Prompt v2 重录后 5 张图 ≥3/5 ✅
- ✅ 本地手工端到端验证 OK（推荐）
- ✅ Phase 1 带入的 4 个 follow-ups 全闭环

## Phase 2 不在本计划内的事

- 小程序前端（Phase 3）
- DeepSeek / Qwen 备用 provider（Phase 2 D9 stub；只有 Claude 不够用时才提前实现）
- 图片 OSS 存储抽象（Phase 4+ 视需要）
- 多进程 / 分布式部署形态（Phase 3 上线前再说）
- 完整 OpenAPI 文档定稿（FastAPI 自动 /docs 够用；Phase 3 与前端对接时再校对）
- 业务监控 / 报表（Phase 3+）

## 风险与回退

| 风险 | 触发 | 回退 |
| --- | --- | --- |
| 信号量 = 2 在多并发场景下卡队列 | T8 集成测试 timeout | 调到 4 重跑，无效再讨论 |
| Prompt v2 重录后跌破 3/5 | T9 | 回退 v1（git revert prompt.py + replay_capture）；Phase 2 退出门豁免 prompt 条款，单算"v1 仍通过" |
| slowapi 与 FastAPI 版本不兼容 | T7 安装失败 | 改 DIY in-memory counter（30 行）；架构层不变 |
| sqlite WAL 在 Windows 上有坑 | T2 测试挂 | 退回普通模式（行级锁），文档化"多 reader 注意性能" |
| 集成测试需要真 LLM | T8 误调到真 provider | 严格用 dependency_overrides 注入 FakeLLMProvider；CI 上 env 不配 ANTHROPIC 信息 |
| Claude CLI 在 backend 进程没 OAuth 登录 | T10 手工跑失败 | T9 README 已文档化；用户重跑 `claude login`，不改代码 |
