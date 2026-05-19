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
