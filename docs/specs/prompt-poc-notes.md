# Phase 1 PoC 迭代记录

> 不是定稿文档。Phase 1 Task 14 把通过的 Prompt 抄到 `app/llm/prompt.py` 后，本文保留作决策痕迹。
> 上游契约：[`docs/specs/report-schema.md`](./report-schema.md)、[`docs/specs/hazards.md`](./hazards.md)
> Provider：Claude CLI（`backend/app/llm/claude_cli.py`），目标模型 Sonnet（实测见下方"模型路由观察"）

## 人工标注 Ground Truth（5 张样图）

| 编号 | 真实隐患（用户标注） | 预期命中类别 |
| --- | --- | --- |
| case_001 | 人字梯超 2 米 | H1 高处坠落 |
| case_002 | 外架与结构间无防护 | H1 / H2 |
| case_003 | 移动式操作平台缺侧向剪刀撑、下支撑 | H4 坍塌 |
| case_004 | 楼梯防护可靠性不足 + 侧边平台无防护 | H1 |
| case_005 | 支模体系梁下加密杆与架体未形成可靠连接 | H4 坍塌 |

> 注：先前 GT 表笔误把"坍塌"标为 H7；按 [`hazards.md`](./hazards.md)，H7 是中毒/窒息，"坍塌"是 H4。已更正。

评判标准：
- ✅ 主隐患识别准确 + 报告"像安全员写的"（用语专业 + 引规范 + 整改可执行）
- ⚠️ 主隐患方向对但措辞 / 严重度 / 类别归类不准
- ❌ 主隐患漏识别 / 严重幻觉规范条款 / JSON 不合规

退出门：5 张图中 ≥ 3 张 ✅。

---

## v1（2026-05-19）

**Prompt 摘要**：见 `backend/scripts/poc_claude.py` 中的 `PROMPT_V1`。

**System prompt**：见 `backend/app/llm/claude_cli.py` 中的 `SAFETY_OFFICER_SYSTEM_PROMPT`。

**5 张图结果**：

| 图 | 解析 | 实际模型 | plain_warning | overall_severity | 命中类别（主在前） | 延迟 (s) | 成本 ($) | 评判 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_001 | L1 | sonnet-4-5 | 梯子快倒，立刻停用加固！ | high | **H1** + H9 + H2 + H10 | 84.6 | 0.107 | ✅ |
| case_002 | L2 (parser 修复后) | opus-4-5 | 临边没护栏，安全网松了，随时能坠人！ | high | **H1×2** + H2 + H9 | 122.2 | 0.156 | ✅ |
| case_003 | L1 | sonnet-4-5 | 脚手架无护栏快倒了，地上全是碎石，危险！ | high | **H1** + **H4** + H2 + H10 + H9 | 93.7 | 0.124 | ✅ |
| case_004 | L1 | opus-4-5 | 安全网破了，楼梯边随时可能坠落！ | high | **H1×2** + H10 | 266.0 | 0.201 | ✅ |
| case_005 | L1 | sonnet-4-5 | 顶部裸灯泡漏电风险极高，立即断电整改 | high | H3 + **H4** + H9 + H10 | 93.2 | 0.117 | ⚠️ |

**汇总**：4 ✅ + 1 ⚠️ + 0 ❌ → **通过率 4/5（达成 ≥3/5 退出门）**。
总成本 $0.705 / 5 张 = 均价 $0.141；纯 Sonnet 均价 ~$0.116，Opus 均价 ~$0.178。

**case_005 标 ⚠️ 的理由**：主 GT（支模体系坍塌）正确识别为 H4，但模型 hazards 数组里把 H3（顶部裸灯泡漏电）排在第一位，plain_warning 也强调 H3 → 模型自己判断"电气风险更立即"，但与人工 GT 主隐患不一致。技术上不算错，是排序逻辑与产品意图未对齐。

---

**问题观察**：

1. **`--model sonnet` alias 非确定性路由到 Opus**（实测 5 张图里 2 张被路由到 `claude-opus-4-5`，成本翻倍 + 延迟显著拉长，case_004 跑了 266s）。原因未明，疑似 Sonnet 配额紧张时 CLI 自动 fallback。**v2 应固定到全名 `claude-sonnet-4-6`** 或 `claude-sonnet-4-5`，绕过 alias 解析。
2. **同类别重复列项**（case_002 / case_004 都给了 H1×2 — "临边无护栏" + "安全网松弛" 拆成两条）。Prompt v1 没明说"同类别合并"，模型按现象拆条。可接受但不够紧凑；可在 v2 加约束"同 category_code 合并为一条 description（分号串接）"。
3. **case_005 plain_warning 与主 GT 不对齐**（模型自主判定 H3 触电比 H4 结构更"立即"）。**v2 应在 prompt 里明确 plain_warning 必须呼应 hazards[0]**，且 hazards[0] 应是最高风险的"结构性"隐患（用语再斟酌）。
4. **`model_meta.latency_ms` 模型自己填的是幻觉值**（3200 或 0），与实际 84-266 秒差几个数量级。Phase 2 backend 路由层必须用真实 `RawLLMResponse.latency_ms` 覆盖；现在不修 prompt（说了模型也不知道真值）。
5. **`--json-schema` 强约束生效**（5 张图里 4 张 L1 直通，第 5 张 L2 直通；0 张需要 reprompt）。
6. **规范引用全部真实**（实测出现的 JGJ59-2011、JGJ80-2016、JGJ130-2011、JGJ46-2005、JGJ59-2011 都是真实国标，未发现编造条款号）。Prompt v1 的"regulation 不允许编造"约束有效。
7. **plain_warning 字数稳定在 12-20 字**，全部在 30 字上限内。
8. **解析失败模式**（T10 阶段已修复）：case_002 markdown 包裹 + 嵌套 hazards → 旧 parser 优先返回内层 hazard dict。已修为"贪心优先 + 候选必须过 Pydantic"，commit 61fc67f。

---

**v2 改动方向**：

1. **模型固定全名**：`CLAUDE_MODEL=claude-sonnet-4-6`（或 4-5，看用户订阅可用版本），绕过 alias 路由。在 `.env.example` 注释里说明 alias 不稳。
2. **Prompt 加同类合并约束**："同一 category_code 下的多条隐患应合并为单条 hazard，description 用分号串接现象，suggestion 涵盖全部整改动作。"
3. **Prompt 加 plain_warning 对齐约束**："plain_warning 必须呼应 hazards[0] 的核心风险；hazards 应按结构性 / 不可逆程度排序，最高风险在前。"
4. **Prompt 明确 model_meta 字段**："`model_meta` 字段值随便填，由后端覆盖。"（避免模型胡编 latency_ms）
5. **不动**：JSON 结构、类别枚举、regulation 约束、字数上限 — 这些 v1 表现良好。

---

## 模型路由观察（疑点）

| 用 `--model sonnet` 实际跑到 | 次数 | 平均成本 | 平均延迟 |
| --- | --- | --- | --- |
| `claude-sonnet-4-5` | 3 | $0.116 | 90 s |
| `claude-opus-4-5` | 2 | $0.178 | 194 s |

CLI 帮助文档说 `sonnet` 是 alias to latest sonnet（按描述应当解析为 `claude-sonnet-4-6`），但实测从未路由到 4-6，只在 4-5 与 opus-4-5 之间漂。**怀疑**：(a) 当前 CLI 版本（2.1.144）的 alias 表里 sonnet 仍指向 4-5；(b) 高负载 / 配额触发时 fallback 到 Opus；(c) 用户订阅未开放 4-6。**v2 建议固定全名，明示该跑哪个**，让成本 / 延迟可预期。

---

## § Phase 1 冻结决策（2026-05-19）

- **冻结版本**：v1（见 [`backend/app/llm/prompt.py`](../../backend/app/llm/prompt.py)）
- **跳过的 task**：
  - T12（Prompt 迭代到 v2/v3）— v1 已达 4/5 退出门，YAGNI 跳过
  - T13（压缩 A/B 实验）— 用户已决定 v0.2 不引入压缩；实验视为 v0.2 prep 工作，按需补
- **v2 改动方向**（v1 frozen，下列待 v0.2 / Phase 2 视需要处理）：
  - `--model` 固定全名而非 alias（避免 fallback 路由）
  - 同类别合并约束
  - plain_warning 与 hazards[0] 对齐
  - model_meta 字段说明"由后端覆盖"

---

## v2（2026-05-19，Phase 2 Task 9）

**Prompt 改动**：基于 v1 实测的 v2 改动方向，给 `ANALYZE_PROMPT` 末尾的约束列表加 3 条：
- 同 `category_code` 合并（不允许同 code 出现两次）
- hazards 按结构性 / 不可逆程度排序，`plain_warning` 必须呼应 `hazards[0]`
- `model_meta` 字段值随便填，由后端覆盖

`PROMPT_VERSION = "v2"`。完整文本见 [`backend/app/llm/prompt.py`](../../backend/app/llm/prompt.py)。

**5 张图实测结果**（用 `scripts.replay_capture --prompt-version v2` 重录）：

| 图 | 解析 | plain_warning | overall | 命中类别（主在前） | 延迟 (s) | 成本 ($) | 评判 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| case_001 | OK（走 structured_output） | 梯子未固定，随时可能倒塌！ | high | **H1** + H9 + H10 | 91.5 | 0.190 | ✅ |
| case_002 | L1 | 边缘缺口敞开安全网松垮，人员随时坠落 | high | **H1** + H9 | 73.2 | 0.092 | ✅ |
| case_003 | L1 | 脚手架随时倒，立即撤离！ | high | **H4** + H1 + H2 + H10 | 174.6 | 0.226 | ✅ |
| case_004 | L1 | 楼梯无栏杆，随时可能坠落！ | high | **H1** + H2 + H9 | 107.6 | 0.131 | ✅ |
| case_005 | L1 | 支撑架缺斜撑，随时可能垮！ | high | **H4** + H1 + H3 + H2 + H9 | 106.6 | 0.153 | ✅ |

**汇总**：**5 ✅ + 0 ⚠️ + 0 ❌ = 5/5（比 v1 的 4/5 提升 1）**。
总成本 $0.793 / 5 = 均价 $0.159（v1 均价 $0.141，略涨；因为 case_001 / case_003 这次跑得较长）。

**v2 改动效果验证**：

1. **同类合并**：v1 的 case_002/004 都出现 H1×2，v2 全部去重为 H1×1（case_002: H1+H9；case_004: H1+H2+H9）。约束生效 ✅
2. **plain_warning ↔ hazards[0] 对齐**：
   - v1 case_003 hazards[0]=H1 plain_warning"脚手架无护栏..."；v2 hazards[0]=H4 plain_warning"脚手架随时倒"（呼应 H4 坍塌）✅
   - v1 case_005 plain_warning 强调 H3 电气；v2 hazards[0]=H4 plain_warning"支撑架缺斜撑"（呼应 H4 GT）✅
3. **model_meta 由后端覆盖**：service 层 `report.model_copy(update={"model_meta": real_meta})` 也兜底了；prompt 一层是给模型的"别浪费 token 在这里"提醒 ✅

**v2 顺手暴露的另一个生产 bug（commit 同 T9 修）**：

`--json-schema` 在 v2 实测里出现新行为：CLI 把结构化结果落在 `envelope.structured_output`（dict）而不是 `envelope.result`（str 空）。`ClaudeCLIProvider` 原本只读 `result` → case_001 第一次解析失败。修复：优先读 `structured_output`（序列化回 JSON 字符串），回退到 `result`；都缺时抛 `LLMCallError`。新增单测覆盖。

**遗留小问题**：v2 case_002 把 v1 识别到的 H2（物体打击：钢筋端头无防护）丢了，只剩 H1+H9。主 GT（H1 临边无防护 + 部分 H2）命中一半。属于"模型选择性识别"，prompt 约束没法精准控制。**v0.2 视产品反馈再决定是否硬加 H2 提示词。**

---

## § Phase 1 退出门总结（2026-05-19）

**通过率：4 ✅ + 1 ⚠️ + 0 ❌ = 4/5（达成 ≥3/5 退出门）**

| 维度 | 结论 |
| --- | --- |
| 最终 Prompt 版本 | v1（[`backend/app/llm/prompt.py`](../../backend/app/llm/prompt.py)） |
| LLM 选型 | Claude CLI（subprocess 包装 `claude -p`），目标 Sonnet；实测受 alias 路由影响有时落到 Opus |
| 图像处理 | 不压缩 / 不缩放（≤15MB 原图直传） |
| 单元测试 | **42 passed, 0 failed, 0 skipped** |
| 静态检查 | ruff check . / mypy app/ scripts/ tests/conftest.py 全 clean |
| Phase 1 总成本 | 估算 ~$1.5（含实验 / smoke test / T10 5 张图 / retries） |
| 累计 commit | 17 个（含 1 个 LLM provider pivot + 2 个 bug fix） |

**带入 Phase 2 的已知问题（不阻塞 Phase 1 退出）：**

1. `--model sonnet` alias 非确定性 → Phase 2 接 HTTP / config 时固定全名（`claude-sonnet-4-5` 或 4-6）
2. Prompt v1 同类隐患拆条 + plain_warning 排序与 hazards[0] 偶尔不对齐 → v2 改动方向已记录，按需迭代
3. 子进程方式部署耦合到 "本机装了 claude CLI 且已 OAuth 登录"；可部署面收窄 — Phase 2 评估生产形态时正视
4. 60-260s 单次延迟 → Phase 2 异步轮询架构（已在设计稿 §2.5）覆盖此场景

**Phase 1 没做、按规划属 Phase 2 / 3 的事**（不算遗漏）：

- FastAPI 路由 / SQLite 存储 / 后台任务 / 错误中间件（Phase 2）
- `app/config.py` pydantic-settings（脚本暂用 `os.environ`，Phase 2 切换）
- 图片校验 service（Phase 2，因为它服务于 HTTP 入参）
- 第二个 provider（Phase 2 D9 stub，仅在 Claude 不够用时才提前实现）
- 任何前端代码（Phase 3）

**Phase 1 PASS。可进入 Phase 2 brainstorming。**
