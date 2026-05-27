# v2 路径部署文档

> 改造计划 §六 验收项之一。覆盖 Python 环境、依赖、Claude Code 登录、Skill 库部署、启动命令、smoke 验证。
> v1 部署不变，本文只补 v2 增量步骤。

## 前置条件

| 项 | 要求 | 验证命令 |
|---|---|---|
| Python | ≥ 3.11 | `python --version` 或 `uv python list` |
| uv | ≥ 0.5 | `uv --version` |
| Claude Code CLI | 已安装且**已登录** | `claude --version` + `claude /status` |
| Claude 订阅 | Pro / Max / Team / Enterprise 任意 | 同上 |

**关键**：v2 通过 Claude Agent SDK 走本地 `claude` 子进程 + 订阅额度，**不需要** `ANTHROPIC_API_KEY`。
登录态在用户 home 下（Mac `~/.config/claude/`、Windows `%USERPROFILE%\.claude\`），CI/容器部署需要把登录态文件挂进去或先 `claude login`。

## 依赖安装

`backend/pyproject.toml` 已加 `claude-agent-sdk>=0.1`。

```bash
cd backend
uv sync --extra dev          # 装运行 + dev deps
```

验证 SDK 能调通本地 Claude：
```bash
uv run python scripts/verify_sdk.py
# 期望：打印一段 Claude 模型的回答；失败时报 CLINotFoundError / ProcessError
```

## Skill 库部署

v2 启动时按 `Settings.safety_skills_root`（默认 `<repo_root>/safety_skills/`）加载知识库。

**首次部署**：把 `safety_skills.zip` 解压到仓库根。
压缩包文件名是 UTF-8 但**未设 ZIP UTF-8 flag**，Windows Explorer / `Expand-Archive` 会解出乱码名；
Python 标准库走 cp437 → utf-8 重解码可以正确解压：
```bash
uv run --project backend python -c "
import zipfile
from pathlib import Path
with zipfile.ZipFile('safety_skills.zip') as z:
    for info in z.infolist():
        if not (info.flag_bits & 0x800):
            info.filename = info.filename.encode('cp437').decode('utf-8')
        z.extract(info, '.')
"
```

或者直接通过 git pull 拿到已落库的 `safety_skills/` 目录。

**验证完整性**：17 个文件齐全（1 L1 + 4 shared + 12 scenarios）：
```bash
cd backend
uv run pytest tests/unit/test_safety_agent_loader.py -q
# 期望：8 passed
```

## 环境变量

复制 `.env.example` → `.env`，关键 v2 字段：

```bash
AGENT_MODEL=claude-opus-4-7         # 不要用 sonnet alias
AGENT_TIMEOUT_SECONDS=360           # smoke 实测 ~250s，留 110s 余地
AGENT_MAX_TURNS=15
# SAFETY_SKILLS_ROOT=safety_skills  # 默认就是这个，自定义路径时再设
```

## 启动

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

或用现有的 `npm run dev:backend`（仓库根 `package.json` 已通过 `scripts/start-backend.mjs` 包装好）。

## 前端部署：把 v2 流量打开

后端跑起来之后用户**默认不会走 v2** —— 前端 `miniprogram/src/config.ts` 里的 `V2_TRAFFIC_SHARE` 控制 `createInspection` 随机分流到 `/api/v1/inspections` 还是 `/api/v2/analyze`。

```ts
// miniprogram/src/config.ts
export const V2_TRAFFIC_SHARE = 1.0;  // 0 ~ 1.0；编译期固化进 bundle
```

**关键约束**：这是个**编译期常量**（不走 `process.env` / DefinePlugin），改完必须**重新打包**才能生效。运行时 patch / 远程下发不可能。

灰度节奏（按 `docs/specs/v2-rollout.md` §一）：

| 阶段 | `V2_TRAFFIC_SHARE` | 观察期 | 通过条件 |
|---|---|---|---|
| 内部试用 | 1.0 | 1 周 | 安全员/项目经理用真实图试用，badcase < 10/天 |
| 灰度 10% | 0.10 | 1-2 天 | `failed` 率 ≤ v1；P95 latency ≤ 6 min |
| 灰度 50% | 0.50 | 3-5 天 | 同上 + 用户主观满意度无明显回退 |
| 全量 | 1.0 | 持续 | v1 继续保留作为 fallback 30 天，不下线 |

**改 → 部署完整流程**：

```bash
# 1. 改常量
$EDITOR miniprogram/src/config.ts

# 2. H5 重新打包（生产环境 base URL 由 TARO_API_BASE_URL 注入）
cd miniprogram
TARO_API_BASE_URL=https://api.example.com pnpm build:h5
# 产物在 miniprogram/dist/

# 3. 微信小程序：在 Taro Devtools 重新构建发版（同源 V2_TRAFFIC_SHARE）
pnpm build:weapp

# 4. 把 dist/ 推上静态服务器（nginx root 指向的路径）
rsync -av --delete miniprogram/dist/ scout@PROD:/opt/safety-scout/h5/
```

**回退**：把 `V2_TRAFFIC_SHARE` 改回 `0`、重新打包 + 推上去即可，**后端代码不必动**。v1 路径全程保留作为 fallback。

**验证当前生产是哪条路径**：用户上传一张图，看浏览器 DevTools Network 里 POST 命中的是 `/api/v1/inspections` 还是 `/api/v2/analyze`；或检查报告页 URL 是否含 `?v=2`。

## smoke 验证 v2 端到端

跑一张 fixture 图，验证 SDK + tools + Skill 全链路：
```bash
cd backend
uv run python scripts/v2_smoke.py 1 --timeout 360
# 期望：~4 分钟内返回 6-8 项 findings + 命中 4-5 个场景；落盘 _v2_smoke_last.json
```

trace 模式可以看 Agent 每一步消息流（首次部署排错用）：
```bash
uv run python scripts/v2_smoke.py 1 --trace --timeout 360
# 打 SystemMessage / AssistantMessage / ToolUseBlock / ResultMessage 时间戳
```

## 监控

`logger=app.safety_agent.tools` 上的 `extra.metric` 字段（见 `docs/specs/v2-api-contract.md` 末尾一览）：
- 命中率 `v2.tool.load_scenario.hit` / 失败 `unknown_id`
- 报告校验失败 `v2.tool.submit.{json_error,schema_error,empty}`
- 报告通过 `v2.tool.submit.accepted` 携带 severity_distribution + scene_detected

`logger=app.services.inspection_v2` 在 succeeded 时输出 `latency_ms / tool_calls / scenarios / findings / input_tokens / output_tokens / cost_usd`。

接入 ELK / Loki 时按 `metric` 字段做聚合即可（不需要额外 metrics SDK）。

## 部署期常见问题

| 症状 | 原因 | 处理 |
|---|---|---|
| `CLINotFoundError` | `claude` 不在 PATH | 检查 `claude --version`；Windows 上有时是 `%LOCALAPPDATA%\..\claude.cmd` |
| `ProcessError ... not logged in` | Claude CLI 没登录 / 登录过期 | `claude login`；CI 把 ~/.claude 挂载或预登录 |
| Agent 超时 | `AGENT_TIMEOUT_SECONDS` 太短或订阅 rate limit | 临时提到 540s；rate limit 5h 窗口刷新 |
| `FileNotFoundError: safety_skills/_l1_core/L1_必查清单.md` | zip 解压用了不支持中文名的工具 | 用本文上面的 Python 解压方法重做 |
| Windows uvicorn `--reload` + 子进程 NotImplementedError | SelectorEventLoop 不支持 subprocess | `app/main.py` 已强制 ProactorEventLoop，确认入口未绕过 |
