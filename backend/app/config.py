"""应用配置 —— 通过 `pydantic-settings` 从环境变量 / `.env` 加载。

字段对齐 `docs/plans/2026-05-18-架构-design.md` §2.3 的 `Settings` 类，
并融入 Phase 1 退场总结里两个 follow-ups（见 `docs/specs/prompt-poc-notes.md`）：

1. `claude_model` 默认值固定为 **全名** `claude-sonnet-4-5`，不再用 `sonnet` alias —
   Phase 1 实测 alias 在某些登录态下会被路由到 Opus，单次调用成本翻倍且行为不一致。
2. `claude_timeout_seconds` 默认从 180 上调到 300 —— Phase 1 `case_004` 实测耗时 266s；
   配套 `backend_hard_timeout_s=320 > claude_timeout_seconds`、
   `timeout_ms=330000 > backend_hard_timeout_s*1000`，把"模型超时 → stdlib 超时 →
   前端轮询放弃"的三道闸门留出余地，避免前端先于后端放弃。

`get_settings()` 用 `@lru_cache` 保证整个进程拿到同一份 Settings 实例 ——
路由 / DI / 后台 runner 都从这个单一入口取值，单测里需要重置时主动调
`get_settings.cache_clear()`。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo_root = backend/../ —— config.py 在 backend/app/ 下，往上两级到仓库根
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """运行期配置。字段名 = 环境变量名（大写后）。"""

    # === LLM provider 开关（v1 路径专用）===
    # 业务粒度的二选一：claude_cli | doubao。
    # 默认 claude_cli —— 现有部署不传环境变量也保持原行为。
    # provider 内部具体走哪个模型（sonnet/opus / 火山 endpoint id）各自归各自的字段管。
    # 注意：v2 路径（/api/v2/analyze）不受此开关影响，固定走 Claude Agent SDK。
    llm_provider: Literal["claude_cli", "doubao"] = "claude_cli"

    # === Claude CLI provider（v1）===
    claude_cli_path: str = "claude"
    # 全名，不用 sonnet alias —— Phase 1 实测 alias 会 fallback 到 Opus
    claude_model: str = "claude-sonnet-4-5"
    # 从 Phase 1 的 180 上调；case_004 实测 266s
    claude_timeout_seconds: int = 300

    # === Doubao (火山方舟) provider（v1 alt）===
    # API key 从火山方舟控制台拿；未配置时若选中 doubao，dependencies.get_llm_provider
    # 启动即抛 ValueError，避免请求时才报错。
    doubao_api_key: str = ""
    # 火山方舟的 model 字段：可以填用户账号下自建的 endpoint id（如 ep-2026...），
    # 也可以直接填公共模型名。默认给一个公共 vision 模型，配上 DOUBAO_API_KEY 即可跑；
    # 想换模型 / endpoint 时再覆盖 DOUBAO_MODEL。
    doubao_model: str = "doubao-1-5-vision-pro-32k-250115"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    # HTTP 调用比 Claude CLI 子进程短得多；120s 已含一次 reprompt 余量
    doubao_timeout_seconds: int = 120

    # === Agent SDK (v2) ===
    # v2 默认 opus-4-7。曾尝试切 sonnet-4-6 找速度，**两套架构（structured output
    # 和 submit_safety_report 工具）实测都不可用**：
    #   - Sonnet + structured output: 不会用 CLI 虚拟工具 StructuredOutput，
    #     5 次 retry 全空、504s 超时
    #   - Sonnet + submit 工具: 即使 thinking=0 + 400s timeout 也跑不完单图
    # "Sonnet 3-4× 快于 Opus"在本场景（36k cached prompt + 多轮 tool + 复杂嵌套
    # JSON）下不成立 —— 推测 Sonnet 处理超长 cached prompt 的吞吐显著低于宣传值。
    # 当前 Opus + submit 工具实测 115s 端到端，比 structured output 路径快 ~5s。
    # 不用 sonnet alias —— 同 v1 教训
    agent_model: str = "claude-opus-4-7"
    # Agent 多轮 tool 调用比单次慢；优化后（inline skills + structured output +
    # extended thinking + sonnet）目标 < 60s；保守 timeout 留余地。
    agent_timeout_seconds: int = 360
    # 最大工具调用回合数；防止死循环
    agent_max_turns: int = 15
    # Extended thinking 预算（tokens）。thinking tokens 走专门通道、不计 output_tokens、
    # 不发到用户可见的回复里。开启后模型可以"想清楚再说"，但用户看到的输出只有最终 JSON。
    # 0 = 禁用 extended thinking；建议范围 2000-8000（推理深度 vs 成本/延迟平衡）。
    # 默认从 8000 下调到 2000：实测对工地图分析推理深度足够，且能省 ~10-15s
    # 延迟（thinking tokens 计入 output_tokens 总数，按 output 速率生成）。
    agent_thinking_budget_tokens: int = 2000
    # Native structured output：API 直接强制返回符合 JSON schema 的最终回复，
    # 省掉 submit_safety_report 工具调用那一轮 + 模型 wrap-up 文本（实测可省 ~15s）。
    # 关闭可回退到 v0 行为（保留 submit 工具），但本仓库当前已删除该工具实现，
    # 关闭等于跑不通 —— 留 flag 只为方便日志里读出"当前用的什么模式"。
    agent_use_native_structured_output: bool = True
    # Skill 库根目录；默认 = 仓库根/safety_skills（zip 解压位置）
    safety_skills_root: Path = _REPO_ROOT / "safety_skills"
    # SkillLoader 缓存 TTL（秒）。默认 60s —— 安全工程师 git pull 后下次请求
    # 命中重建，无需重启 backend。设 0 退化为"每请求重建"；
    # 设很大（如 86400）= 永久缓存（接近旧 lru_cache 行为，需手动重启清缓存）。
    safety_skills_cache_ttl_s: int = 60

    # === Storage ===
    sqlite_path: str = "local_data/safety_scout.db"
    upload_dir: str = "uploads"

    # === Image upload ===
    max_image_mb: int = 15  # 与架构 §4.4 + .env.example 一致

    # === Async polling（前端用） ===
    poll_interval_ms: int = 2000
    # 前端轮询总时限 > backend_hard_timeout_s * 1000
    timeout_ms: int = 330000

    # === Backend ===
    # > claude_timeout_seconds，留给 stdlib 余地
    backend_hard_timeout_s: int = 320
    rate_limit_per_minute: int = 10

    # === Quality Tracking · Layer 2 LLM-as-Judge ===
    # 评判模型必须 ≠ 被测模型 —— 防 self-preference bias（doc §4.3）。
    # 被测 opus-4-7，默认 judge 用 sonnet-4-5（更便宜 ~1/5、评判能力强）。
    # 跨厂商需要时改 doubao / openai。
    judge_model: str = "claude-sonnet-4-5"
    # judge 调用超时（pairwise 评一对 + 含图片，120s 足够）
    judge_timeout_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """进程单例 Settings —— 路由 / DI / 后台 runner 统一入口。"""
    return Settings()
