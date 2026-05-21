# Phase 4 A/B 基线数据（首批，case_001）

> **改造计划 §4 验收门**：召回率 ≥30% 提升、致命漏报 = 0、所有输出 JSON 可解析。
> 数据采集脚本：`backend/scripts/v1_vs_v2_ab.py`，落盘 `backend/scripts/_ab_results/`。

## 已采集（1/5）

### case_001 — 人字梯被当单梯靠墙使用

| 指标 | v1 (ClaudeCLIProvider 单轮) | v2 (Agent SDK + Skill) | 差异 |
|---|---|---|---|
| JSON 解析成功 | ✅ | ✅ | — |
| 隐患条目数 | 2 | **7** | **+250%** |
| `uncertain` 项 | (v1 无此概念) | 13 | 模型自识无法判断的项 |
| 规范条款引用率 | 50% (1/2) | **100%** (7/7) | +50pp |
| 严重度分档 | high=1, low=1 | 重大=1, 较大=2, 一般=3, 低=1 | 4 档全用 |
| 命中场景 ID | — | S05, S06, S10, S12 | 4 个相关 L2 主动加载 |
| 整体风险等级 | (v1 字段 `overall_severity=high`) | 较大 | — |
| 单图耗时 | 92.6s | 231.3s | +149% |
| Tool 调用数 | 0 (CLI 单轮) | 7 (1 Read + 4 load + 1 ToolSearch + 1 submit) | — |
| 单图成本（订阅外估算） | — | $0.5569 | 受订阅 ratecard 影响 |
| Input/Output tokens | (CLI 未结构化暴露) | 19 / 12005 | 输出主要在 submit 报告 JSON |

#### v2 比 v1 多识别的 5 项隐患（核心证据）

v1 报告里只有：高坠（人字梯）+ 一项次要项。
v2 同图基础上多检出：

| check_id | severity | 内容 |
|---|---|---|
| S06-E02 | 重大 | 人字梯被当单梯靠墙斜立，结构错用 |
| C03 | 重大 | 攀登路径旁电线裸露悬挂 |
| D04 | 较大 | 梯脚立于不平整 + 散落杂物的地面 |
| A03 | 一般 | 工人未佩戴下颚带 |
| F05 | 一般 | 现场建筑垃圾未清理（文明施工） |
| S10-B01 | 一般 | 砖块堆放靠近临边 |

每条 v2 finding 都带：`check_id`（清单编号）+ `location`（图片相对位置）+ `regulation`（具体条款）+ `action`（动作可执行）+ `confidence`，渲染层信息密度显著高于 v1。

#### Agent 行为观察（trace 模式截屏）

```
[ 15s] Read tool 读图
[ 16s] ToolSearch 发现 MCP 工具（Claude Code 默认先 search 再 use）
[ 50s] 整图描述 + 九宫格扫描
[ 52s] 一次性 load_scenario_skill ×5 (S05/S06/S07/S10/S12)
[132s] Step 3+4 清单逐项核查 + 致命强化复检
[236s] submit_safety_report 提交完整 JSON
[249s] 流结束
```

`ToolSearch` 这一步是 Claude Code 内置的"工具发现"行为，每次冷启动会多花 ~1-2s。
Skill `cot_instructions` 中的 Step 编号被 Agent 完整遵循。

## 已尝试但失败（1/5）

### case_002 — scaffolding_and_structural_components_not_protected (1.4MB)

| 路径 | 结果 | 备注 |
|---|---|---|
| v1 | FAIL: `Claude CLI 非零退出 (rc=1)` | stderr 空；典型表现是订阅 rate limit 命中或 stdout schema 不合规 |
| v2 | FAIL: `LLMTimeoutError (>360s)` | 没拿到任何 ResultMessage；超时位置不明（需要 --trace 复跑定位） |

**怀疑诱因**（按可能性排序）：
1. 紧邻 case_001 跑完（~$0.56 + 多次 v2 smoke），Claude 订阅 5h 窗口剩余额度不足
2. case_002 图片较复杂（1.4MB vs case_001 711KB），Agent 多轮分析超过 360s
3. v1 CLI 偶发非零退出（已有的 [phase 2 prompt-poc-notes] 描述过类似抖动）

**复跑前要做的**：
- 等 5h 窗口刷新后重跑（最稳）
- 或：把 `agent_timeout_seconds` 临时提到 540s，再用 trace 模式看 v2 卡在哪
- 或：先用 case_003/004/005 探测，分布式确认是否 case_002 特异

## 待采集（3/5）

- case_003 mobile_operation_platform_lacks_lateral_diagonal_braces_lower_supports
- case_004 stair_guard_unreliable_there_no_protection_on_the_side_platform
- case_005 reinforcing_rods_under_beams_formwork_system_were_not_securely_connected_to_the_scaffolding

跑法：
```
uv run python scripts/v1_vs_v2_ab.py            # 全跑（~25min）
uv run python scripts/v1_vs_v2_ab.py --only 2   # 只跑 case_002
```

每张图增量写 `_ab_results/_summary.json` —— 中途断网/手动停掉，已跑完的数据不丢。

## 初步结论（待补足 4 张图后修订）

- ✅ JSON 解析率：1/1 v2 用 ReportV2Payload 校验通过（→ 验收门 "all JSON 可解析" 看起来稳）
- ✅ 召回率（隐患数）：v2 7 vs v1 2，远超 +30% 目标
- ✅ 规范引用：v2 100% vs v1 50%，专业度提升明显
- ⚠️ 致命漏报：case_001 无 ground truth 标注，无法机械验证 = 0；需要人工对照
- ⚠️ 成本：v2 单图 $0.56；按 plan §4.4 估的 1500-3000 output tokens 实际是 ~12k，超预期 4 倍
- ⚠️ 耗时：v2 比 v1 慢 ~2.5x，与 plan §4.4 预估的 30-60s 也有差距（实测 230s）

下一步：补完 4 张图 + 人工标注 GT → 计算实际召回率与漏报率。
