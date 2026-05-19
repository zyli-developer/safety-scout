# Safety Scout · 工地安全隐患识别小程序

面向工地安全员的 AI 隐患识别工具：拍一张现场照片，由多模态 LLM 分析出潜在隐患，并给出专业、可执行的整改建议。

## 目标用户

工地安全员。强调：
- **流程极简**：理想路径只有「拍照 → 等待 → 看报告」三步。
- **结论专业**：输出要符合建筑施工安全规范用语，便于安全员直接转给班组整改。

## 技术栈

| 模块 | 选型 | 说明 |
| --- | --- | --- |
| 小程序前端 | [Taro](https://taro-docs.jd.com/) + React + TypeScript | 编译到微信小程序；后续可一码多端（Phase 3） |
| 后端 API | FastAPI (Python 3.11+) | 异步轮询：POST 创建任务、GET 拉状态；BackgroundTasks 跑 LLM |
| 多模态 LLM | **Claude CLI**（本地 `claude -p` 子进程，OAuth 登录态） | 模型 `claude-sonnet-4-5`；Phase 1 实测在 5 张样图上通过 4/5 |
| 存储 | SQLite（stdlib）+ 本地文件系统 | 任务记录走 SQLite (WAL)；图片落 `backend/uploads/`，7 天 GC |

## 目录结构

```
safety-scout/
├── miniprogram/    # Taro 小程序工程
├── backend/        # FastAPI 后端服务
├── docs/           # 设计文档、Prompt、隐患规范资料
├── .gitignore
└── README.md
```

## 核心用户流程

1. 进入小程序首页 → 点「拍隐患」大按钮
2. 调起相机拍照（或从相册选）
3. 上传至后端 → 后端调用多模态 LLM
4. 展示结构化报告：隐患项、风险等级、依据条款、整改建议
5. 可保存 / 导出 / 转发

## 部署

**硬约束**：后端进程必须运行在装有 `claude` CLI 且**已 OAuth 登录**的机器上。原因：

- LLM 调用通过 `subprocess` 包装本地 `claude -p` 实现（见 `backend/app/llm/claude_cli.py`），无 API Key 配置入口
- 每次请求会 fork 一个 `claude` 子进程，复用用户的 OAuth token；token 走 macOS Keychain / Windows Credential Manager / Linux libsecret
- 部署目标机器需要：
  1. 装 `claude` CLI（参见 https://claude.com/claude-code 安装指引）
  2. 跑一次 `claude login` 并完成浏览器授权流程
  3. 验证 `claude --version` 与 `claude -p "ping" --output-format json` 都能成功
- **不能简单 docker 化**或丢到任意云主机：除非容器里也装 `claude` 并能让 OAuth token 生效（目前 Anthropic 没给"headless 服务账户"流程）
- 适用形态：本机直跑 / SSH 上去的固定 VPS / 装了 Claude Code 的 dev 机；不适合 serverless / Kubernetes / 多副本横向扩展

如果后续要解耦此依赖，需要：
- 切到 Anthropic 官方 API（`anthropic` SDK + API Key）
- 或加一个 provider（DeepSeek / 豆包 / 通义），用 `LLMProvider` Protocol 替代 `ClaudeCLIProvider`

**配置**：复制 `backend/.env.example` 为 `backend/.env`，无 secret 需要填；关键字段：
- `CLAUDE_MODEL=claude-sonnet-4-5`（用全名，不要用 `sonnet` alias —— Phase 1 实测 alias 有时被路由到 Opus，成本翻倍）
- `CLAUDE_TIMEOUT_SECONDS=300`（Phase 1 实测复杂场景跑到 266s，留余地）
- `MAX_IMAGE_MB=15`、`RATE_LIMIT_PER_MINUTE=10`

**本地起后端**：
```bash
cd backend
uv venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m uvicorn app.main:app --reload
# 验证：curl http://127.0.0.1:8000/api/v1/healthz → {"status":"ok"}
```

## 项目进度

- ✅ **Phase 1**：LLM 适配层 + Prompt v1 冻结 + record-replay 基础设施（PR #1）
- ✅ **Phase 2**：FastAPI 后端骨架 + 集成测试 + Prompt v2（当前分支 `feat/phase-2-backend`）
- ⏳ **Phase 3**：Taro 小程序前端（拍照页 + 报告轮询页）
