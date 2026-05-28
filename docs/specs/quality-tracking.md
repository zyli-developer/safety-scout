# 报告质量追踪体系（quality-tracking）

> 设计文档兼 PRD/roadmap。三个 GitHub issue（layer 1 / 2 / 3）按本文档分章节实现，
> 同一 PR 提交。
>
> 维护对象：`feat/quality-tracking` 分支
> 状态：**Draft —— 待 review**
> 最后更新：2026-05-27

## 1. 问题与目标

### 1.1 现状

- 一次 v2 图片分析端到端 ~3min，用户反馈"太慢"
- prompt / skill 改动后，**无法机械证明**"质量没退步"或"质量真的提升"
  —— 全靠肉眼对比单张图的输出
- 历史分析的指标只散落在 `inspections.model_meta_json` 文本里，
  无法 SQL 聚合，无法画趋势

### 1.2 目标（验收门）

| # | 目标 | 完成判据 |
|---|---|---|
| G1 | 每次分析的关键指标可 SQL 查询 | 新表 `inspection_metrics` 落地、`dump_metrics.py` 输出 CSV |
| G2 | 任意两个 prompt 版本能机器判定 "哪个更好" | `judge_versions.py` 输出含 win-rate 表 + verdict（ACCEPT/REJECT） |
| G3 | 安全员能在小程序看到质量趋势 | history 页新 tab；`GET /api/v1/quality/trend` 返聚合数据 |

### 1.3 非目标（明确不做）

- ❌ 自动调整 prompt（AutoML）—— 本期只**衡量**，调整仍由人工
- ❌ 人工 fixture GT 标注 —— 已决定走 LLM-as-judge 替代
- ❌ 实时 A/B 路由（流量切分按 prompt 版本）—— 跨当前架构边界
- ❌ 修复 3min 延迟 —— 本文档只提供测量框架，**不**包含优化实现

## 2. 三层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3 · 用户层（HTTP + Frontend Dashboard）                │
│   GET /api/v1/quality/trend                                  │
│   miniprogram history 页 "质量趋势" tab                      │
└───────────────────────▲─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│ Layer 2 · 评判层（LLM-as-Judge, pairwise + 位置去偏）        │
│   judge_service.py / quality_judgments 表 / judge_versions.py│
└───────────────────────▲─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│ Layer 1 · 数据层（每次分析记原子指标）                       │
│   inspection_metrics 表 / dump_metrics.py                    │
│   写入点：services/inspection_v2.py + services/inspection.py │
└─────────────────────────────────────────────────────────────┘
```

下沉原则：上层都从 Layer 1 + 现有 `inspections` / `feedbacks` 表读，
新表只有 2 张（`inspection_metrics` + `quality_judgments`）。

## 3. Layer 1 · 数据层

### 3.1 `inspection_metrics` 表

每次分析（含失败）写一行。与 `inspections` 1:1。

```sql
CREATE TABLE inspection_metrics (
  inspection_id        TEXT PRIMARY KEY REFERENCES inspections(id),
  -- 版本指纹（缺这个就无法说"哪个 prompt 改动让我变好了"）
  api_version          TEXT NOT NULL,    -- 'v1' | 'v2'
  prompt_version       TEXT NOT NULL,    -- v1: PROMPT_VERSION; v2: skill_index_version
  skill_index_version  TEXT,             -- safety_skills/_index.json 顶层 version
  model                TEXT NOT NULL,    -- claude-opus-4-7 / sonnet-4-5 / doubao-...
  -- 输入指纹
  image_sha256         TEXT NOT NULL,    -- 同图复跑去重 / 一致性分析
  image_bytes          INT NOT NULL,
  run_group_id         TEXT,             -- 同图 N 次复跑绑成一组（NULL = 单跑）
  -- 性能 / 成本（从 model_meta_json 摘出来变列，方便 SQL）
  total_elapsed_ms     INT,
  input_tokens         INT,
  output_tokens        INT,
  cache_read_tokens    INT DEFAULT 0,    -- 启用 prompt cache 后非 0
  cost_usd             REAL,
  tool_calls           INT DEFAULT 0,
  scenarios_loaded     TEXT,             -- JSON array, v1 为空
  -- 结果形状（从 report_json 预提，避免每次查询 JSON parse）
  finding_count        INT DEFAULT 0,
  no_finding_count     INT DEFAULT 0,
  uncertain_count      INT DEFAULT 0,
  severity_dist_json   TEXT,             -- {"重大":1,"较大":2,...}
  is_major_count       INT DEFAULT 0,
  major_basis_filled_count INT DEFAULT 0,
  reg_coverage         REAL,             -- regulation 非空的 finding 占比
  -- 状态
  status               TEXT NOT NULL,    -- 'succeeded' | 'failed' | 'timeout'
  error_code           TEXT,
  recorded_at          TEXT NOT NULL
);
CREATE INDEX idx_im_prompt_ver  ON inspection_metrics(prompt_version);
CREATE INDEX idx_im_image_sha   ON inspection_metrics(image_sha256);
CREATE INDEX idx_im_recorded_at ON inspection_metrics(recorded_at);
CREATE INDEX idx_im_status      ON inspection_metrics(status);
```

**幸存者偏差防御**：`status='failed'` / `'timeout'` 也写一行，
否则只看成功样本会高估质量。

**为什么不内联到 `inspections`**：
- `inspections` 是业务表，schema 改动牵动 v1/v2 路由 + 前端；指标表独立避免冲突
- 后期可以删 7 天前的指标行而保留 inspections（GC 策略不同）

### 3.2 写入点

| 路径 | 文件 | 时机 |
|---|---|---|
| v1 success | `services/inspection.py::run_inspection` | succeeded 后、`update_succeeded` 之后 |
| v1 fail | `services/inspection.py::run_inspection` | failed 后、`update_failed` 之后 |
| v2 success | `services/inspection_v2.py::run_inspection_v2` | succeeded 后 |
| v2 fail | `services/inspection_v2.py::run_inspection_v2` | failed 后 |

新建 `app/storage/metrics_repo.py`：

```python
def record(
    conn, inspection_id, *,
    api_version, prompt_version, skill_index_version, model,
    image_sha256, image_bytes, run_group_id=None,
    elapsed_ms, input_tokens, output_tokens, cache_read_tokens=0,
    cost_usd, tool_calls, scenarios_loaded,
    report,                       # ReportPayload | ReportV2Payload | None
    status, error_code=None,
) -> None: ...
```

`report` 内部 derive `finding_count` / `severity_dist_json` / `reg_coverage` 等
预提字段，调用方不用关心。

### 3.3 版本指纹来源

| 字段 | 来源 |
|---|---|
| `prompt_version` (v1) | `app.llm.prompt.PROMPT_VERSION` |
| `prompt_version` (v2) | `safety_skills/_index.json` 的 `version`（当前 "1.0.0"） |
| `skill_index_version` (v2) | 同上 |
| `model` | `Settings.claude_model` (v1) / `Settings.agent_model` (v2) |
| `image_sha256` | `hashlib.sha256(image_bytes).hexdigest()`，在 service 层算 |

### 3.4 `scripts/dump_metrics.py`

```bash
uv run python scripts/dump_metrics.py \
    --since 2026-05-01 \
    --prompt-version v7 \
    --status succeeded \
    -o metrics.csv
```

输出**所有列** + 几个 derived 列（`p_latency_seconds`、`tokens_per_finding`），
让用户用 excel 自己切。

**不**做 UI 分析 —— 用户明确说"让我对数值进行分析"，意思是要原始数据。

### 3.5 验收 checklist（Layer 1）

- [ ] `inspection_metrics` 表幂等创建（`init_schema` 加段）
- [ ] v1 / v2 两条路径各自 success / fail 都写入指标（4 个写入点）
- [ ] `image_sha256` 计算放在 service 层，避免 repo 层重复哈希
- [ ] 单测：
  - `test_metrics_repo.py` —— record / query 基本 CRUD
  - `test_inspection_service_metrics.py` —— 一次 run_inspection 必然产生一行指标
  - `test_inspection_v2_service_metrics.py` —— v2 路径同上
- [ ] `dump_metrics.py` --since / --prompt-version / --status 过滤都工作

## 4. Layer 2 · 评判层（LLM-as-Judge）

### 4.1 `quality_judgments` 表

```sql
CREATE TABLE quality_judgments (
  id                       TEXT PRIMARY KEY,             -- uuid
  image_sha256             TEXT NOT NULL,
  baseline_inspection_id   TEXT NOT NULL REFERENCES inspections(id),
  candidate_inspection_id  TEXT NOT NULL REFERENCES inspections(id),
  judge_model              TEXT NOT NULL,                -- 必须 ≠ 被测模型
  judge_rubric_version     TEXT NOT NULL,                -- judge prompt 自己的版本
  swap_position            INT NOT NULL,                 -- 0 = A=baseline, 1 = A=candidate
  -- 结构化 verdict（judge JSON parse 出来；'A'/'B'/'tie' 已归一化到 baseline/candidate/tie）
  winner_overall           TEXT,                         -- 'baseline'|'candidate'|'tie'
  winner_recall            TEXT,
  winner_precision         TEXT,
  winner_regulation        TEXT,
  winner_action            TEXT,
  judge_confidence         TEXT,                         -- 'high'|'medium'|'low'
  reasoning_json           TEXT,                         -- judge 完整返回
  cost_usd                 REAL,
  judged_at                TEXT NOT NULL
);
CREATE INDEX idx_qj_image ON quality_judgments(image_sha256);
CREATE INDEX idx_qj_pair  ON quality_judgments(baseline_inspection_id, candidate_inspection_id);
```

### 4.2 Judge rubric（v1.0）

文件位置：`backend/app/quality/judge_rubric.py`（独立模块，便于版本化）

```
你是一名资深建筑安全总监。下面给你 1 张工地照片 + 两份独立的安全分析报告（A 和 B）。
请独立比较以下 4 个维度，每维度选 winner（A / B / tie）+ 一句话理由：

1. recall —— 谁识别出更多真实存在的隐患（漏报谁少）？
2. precision —— 谁的识别更少误判（描述了图中实际没有的隐患）？
3. regulation_quality —— 谁引用的规范条款更具体、更可信、不编造？
4. action_actionability —— 谁的整改建议更具体、动作可直接落地？

最后给 overall winner + 一句话总结 + 你的 confidence。

约束：
- 你不知道 A / B 哪个是新版本 —— 别推测，只看实际内容
- 若两份基本等价，大方给 tie，不要为决断而决断
- 不要受 finding 数量绝对值吸引 —— 多不等于好，质量更重要
- regulation_quality 重点考察"不编造条款号"，宁缺勿造的引用比看起来很详细但是
  编的好

返回 JSON（**只**返 JSON，无前后缀）：
{
  "by_dimension": {
    "recall":              {"winner":"A|B|tie", "reason":"..."},
    "precision":           {"winner":"A|B|tie", "reason":"..."},
    "regulation_quality":  {"winner":"A|B|tie", "reason":"..."},
    "action_actionability":{"winner":"A|B|tie", "reason":"..."}
  },
  "overall": {"winner":"A|B|tie", "summary":"...", "confidence":"high|medium|low"}
}
```

### 4.3 Judge 模型选型

| 项 | 决定 |
|---|---|
| 模型 | **`claude-sonnet-4-6`** |
| 理由 | 与被测 `opus-4-7` 不同（防 self-preference），评判能力强，价格 1/5 |
| 配置 | `Settings.judge_model: str = "claude-sonnet-4-6"`，可环境变量覆盖 |
| 备选 | 跨厂商时改 `doubao-1-5-vision-pro` 或 `gpt-5-mini`，schema 不变 |

### 4.4 位置去偏 workflow

```python
async def judge_pair(image_bytes, baseline_report, candidate_report) -> Verdict:
    # 跑 2 次，A/B 位置互换
    j1 = await _single_judge(image_bytes, A=baseline_report, B=candidate_report)
    j2 = await _single_judge(image_bytes, A=candidate_report, B=baseline_report)

    # j2 的 winner 翻转回 baseline/candidate 视角
    j2_normalized = _flip_ab(j2)

    if _verdicts_agree(j1, j2_normalized):
        return Verdict(confident=True, **j1)   # 与位置无关 → 可信
    return Verdict(confident=False, status="inconclusive")  # 位置敏感 → 不算数

def _verdicts_agree(a, b) -> bool:
    """overall winner 一致即可；维度细节允许不同。"""
    return a.winner_overall == b.winner_overall
```

只有 `confident=True` 的判定进入聚合统计。`inconclusive` 单独计数，
占比高（>30%）说明 judge 不可靠或两份报告其实差不多。

### 4.5 CLI 入口：`scripts/judge_versions.py`

```bash
uv run python scripts/judge_versions.py \
    --baseline-prompt v6 --candidate-prompt v7 \
    --image-set fixtures \                # 'fixtures' | 'recent:30' | 路径
    --runs-per-image 1 \                  # 同图 N 次（>1 触发 self-consistency 分析）
    --judge-model claude-sonnet-4-6
```

输出（示例）：

```
=== Judge Verdict ===
8 images × (baseline + candidate) = 16 analyses, 16 judge pairs (32 calls with swap)

Overall:
  - candidate wins:   10 / 16 (62.5%)
  - baseline wins:     2 / 16 (12.5%)
  - tie:               3 / 16 (18.8%)
  - inconclusive:      1 / 16 ( 6.2%)  ← swap 后翻转

Per-dimension win rate (candidate vs baseline, ties redistributed):
  - recall:               73% vs 13%    +60pp  ✅
  - precision:            50% vs 38%    +12pp  ✅
  - regulation_quality:   62% vs 25%    +37pp  ✅
  - action_actionability: 50% vs 25%    +25pp  ✅

Latency (p50):
  - baseline:  245s
  - candidate: 148s   -40%  ✅

Total cost: $4.83 (analysis $3.20 + judge $1.63)

Verdict: ✅ ACCEPT candidate
```

### 4.6 接受规则（写死在 `judge_versions.py`，不靠拍脑袋）

verdict = **ACCEPT** 当且仅当全部满足：

| 维度 | 规则 |
|---|---|
| Overall | `candidate_wins - baseline_wins ≥ 3` (避免 1-2 张图噪声) |
| Recall | `winner_recall=candidate` 占比 ≥ `winner_recall=baseline` 占比 |
| Precision | `winner_precision=baseline` 占比 - candidate ≤ 15pp（容忍小幅退化） |
| Inconclusive | ≤ 30%（高于此说明判定不可靠） |
| 性能（可选 gate）| `candidate.p50_latency ≤ baseline.p50_latency`，差值 ≥ -30% |

任一不过 → `verdict: ⚠️ REJECT`，并打印不过的项。

### 4.7 验收 checklist（Layer 2）

- [ ] `quality_judgments` 表幂等创建
- [ ] `judge_rubric.py` 内 `JUDGE_RUBRIC_VERSION = "1.0"`
- [ ] `judge_service.py::judge_pair` 实现 + 位置去偏 + inconclusive 标记
- [ ] `scripts/judge_versions.py` 完整跑通 5 张 fixture
- [ ] 单测：
  - `test_judge_rubric.py` —— prompt 嵌入约束（"返回 JSON" / "盲评"）
  - `test_judge_service.py` —— mock judge 模型，覆盖 agree / disagree / 解析失败
  - `test_judge_accept_rules.py` —— 5 个 verdict 规则逐条覆盖

## 5. Layer 3 · 用户层（HTTP + 前端）

### 5.1 HTTP endpoint

```
GET /api/v1/quality/trend?metric=<name>&group_by=<dim>&since=<iso>
```

| 参数 | 值 | 含义 |
|---|---|---|
| `metric` | `judge_win_rate` / `p50_latency` / `output_tokens` / `finding_count` / `reg_coverage` | 要看的指标 |
| `group_by` | `prompt_version` / `model` / `day` | 分桶维度 |
| `since` | ISO 8601 | 起始时间，默认 30 天前 |

响应：

```json
{
  "metric": "judge_win_rate",
  "group_by": "prompt_version",
  "series": [
    {"group": "v6", "x": "2026-05-15", "value": 0.42, "n": 24},
    {"group": "v7", "x": "2026-05-25", "value": 0.61, "n": 18},
    ...
  ]
}
```

无认证 —— 与现有 v2 API 一致（dev 阶段无登录墙）。

### 5.2 前端 dashboard tab

`miniprogram/src/pages/quality/index.tsx` 新页面，挂在 history 页 TopNav：

```
┌────────────────────────────────────────┐
│  历史  反馈  [质量趋势]                  │
├────────────────────────────────────────┤
│  最近 30 天                  [筛选 ⌄]   │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │  judge win rate (按 prompt 版本) │  │
│  │  v7 ──●──●──●  61% ↑ +19pp      │  │
│  │  v6 ──●──●     42%               │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │  p50 latency                     │  │
│  │  ...                             │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

最小可用：用现成的 SVG 折线图组件（不引图表库，~80 行 React）。
4 张卡片：win_rate / p50_latency / output_tokens / finding_count。

### 5.3 验收 checklist（Layer 3）

- [ ] `routes/quality.py` 加 GET /api/v1/quality/trend
- [ ] `app/services/quality_trend.py` 实现聚合查询（5 个 metric × 3 个 group_by 矩阵）
- [ ] 前端 `pages/quality/index.tsx` 新页 + TopNav 入口
- [ ] 单测：
  - `test_quality_trend_service.py` —— 各 metric × group_by 组合至少一个 case
  - `test_quality_trend_route.py` —— 参数校验 / 默认值
  - 前端：`tests/pages/QualityPage.test.tsx` —— 折线渲染 + 筛选

## 6. 实现节奏

| Step | 范围 | 工作量 |
|---|---|---|
| 0 | review 本文档 → 确认方向 | （你） |
| 1 | 创建 3 个 GitHub issue 跟踪 | 5min |
| 2 | 新分支 `feat/quality-tracking`，Layer 1 实现 + 单测 | ~3h |
| 3 | Layer 2 实现 + 单测 | ~6h |
| 4 | Layer 3 实现 + 单测 | ~4h |
| 5 | 端到端跑一次：5 张 fixture，prompt v7 vs v6 自评 | ~30min |
| 6 | 一个 PR 提交 | 30min |

**总 ~14h** 一次性出 PR。

## 7. 风险与未决

| 风险 | 缓解 |
|---|---|
| Judge 模型自身有 bias（即使 sonnet judge opus） | 位置去偏 + inconclusive 不进统计；用户可换 doubao/gpt 作为二审 |
| Judge 成本：1 次 A/B 评判约 $5-8 | 默认不在 CI 跑，手动 trigger；判定单价远低于人工标注 |
| `inspection_metrics` 表膨胀 | 与 `inspections` 同 GC 策略，7 天后归档（issue #3 实现） |
| 同一图重跑 N 次的成本 | `--runs-per-image` 默认 1；只有显式需要 self-consistency 时才 >1 |

## 8. 不在本文档范围

- 性能优化本身（砍 no_findings 明细、prompt cache 等）—— 等本体系跑起来后由
  数据驱动决定优先级，单独的 issue + PR
- 前端图表库选型升级（如换 ECharts）—— 当前用纯 SVG 渲染即可
- 模型选型自动化（auto-route to faster model when image is simple）

---

**Review 重点**：

1. 三层粒度合不合理？要不要砍 Layer 3，先只做 Layer 1+2 CLI？
2. Judge rubric 4 个维度够吗？要加 `image_relevance`（描述与图片匹配度）吗？
3. 接受规则的阈值（`≥ 3 张图`、`-30% latency`）是否合理？
4. 表结构有没有遗漏字段？
