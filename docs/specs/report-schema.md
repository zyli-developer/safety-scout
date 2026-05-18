# 报告 JSON Schema

> 上游设计稿：[`../plans/2026-05-18-初始化文档-design.md`](../plans/2026-05-18-初始化文档-design.md) §6
> 类别取值依赖：[`./hazards.md`](./hazards.md)

## 性质：前后端共享契约

本文档定义"一次隐患识别"产出的完整 JSON 报告结构。**任何字段增删、类型变更、取值范围调整，必须在同一 PR 内同步修改：**

- 后端组装报告的代码（`app/llm/*`、route handler 序列化）
- LLM Prompt 模版（`prompt.md`，让模型按新 schema 输出）
- 后端 API 契约文档（`api.md`，GET 响应内嵌本结构）
- 前端报告渲染组件（`miniprogram/src/pages/report/*`）

**不允许"代码先走、文档后补"**。

## 完整示例

```json
{
  "inspection_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-18T08:23:11Z",
  "plain_warning": "工人未戴安全帽且站在临边，立刻撤离",
  "summary": "现场存在 3 项高风险隐患，整体风险等级：高。建议立即停工整改。",
  "overall_severity": "high",
  "hazards": [
    {
      "category_code": "H9",
      "category_name": "个人防护缺失",
      "description": "画面中 2 名工人未佩戴安全帽进入施工区",
      "severity": "high",
      "regulation": "《建筑施工高处作业安全技术规范》JGJ 80-2016 第 3.0.3 条",
      "suggestion": "立即责令补齐安全帽并系紧下颌带；班组每日班前会增加 PPE 检查项"
    },
    {
      "category_code": "H1",
      "category_name": "高处坠落",
      "description": "二层楼板边缘缺失防护栏杆，距离地面约 4 米",
      "severity": "high",
      "regulation": "《建筑施工高处作业安全技术规范》JGJ 80-2016 第 4.2.1 条",
      "suggestion": "24 小时内设置高度不低于 1.2m 的临边防护栏杆，挂设警示标志"
    }
  ],
  "model_meta": {
    "provider": "doubao",
    "model": "doubao-vision-1.5-pro",
    "latency_ms": 18432
  }
}
```

## 字段定义

### 顶层字段

| 字段 | 类型 | 必填 | 取值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `inspection_id` | string | 是 | uuid v4 | 一次识别任务的唯一 ID，与 `POST /api/v1/inspections` 创建任务时返回的 ID 一致 |
| `created_at` | string | 是 | ISO 8601 UTC | 任务创建时间 |
| `plain_warning` | string | 是 | 1–30 字，中文，口语化 | 顶部醒目卡片用；**任何工地角色都能秒懂**（含工人）；不出现规范条款编号 |
| `summary` | string | 是 | ≤ 100 字，中文，专业用语 | 面向安全员；整体风险一句话总结 |
| `overall_severity` | string | 是 | `"high" \| "medium" \| "low"` | 定义为 `hazards[]` 中最高 severity；空列表时为 `"low"` |
| `hazards` | array | 是 | 0 ~ N 项 | 隐患明细，允许空数组（无隐患） |
| `model_meta` | object | 是 | 见下 | 模型元信息；前端可忽略，后端必填，用于 A/B 与 latency 监控 |

### `hazards[]` 单项字段

| 字段 | 类型 | 必填 | 取值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `category_code` | string | 是 | `H1` … `H10`（见 [`hazards.md`](./hazards.md)） | 类别编号；不在枚举内视为非法响应，触发 `LLM_PARSE_FAILED` |
| `category_name` | string | 是 | 中文类别名 | 与 `category_code` 对应；供前端直接渲染，避免前端再查表 |
| `description` | string | 是 | ≤ 100 字，中文，专业用语 | 看到的具体现象 |
| `severity` | string | 是 | `"high" \| "medium" \| "low"` | 本条隐患的严重等级 |
| `regulation` | string | 是 | 可为空字符串 `""` | 引用规范条款。**不允许编造**：不确定时必须留空字符串而不是凭空捏造条款号 |
| `suggestion` | string | 是 | ≤ 100 字，中文 | 可执行的整改建议（"24 小时内…"、"立即…"、"班前会…" 这类动作 + 时限） |

### `model_meta` 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | 是 | `"doubao"` \| `"deepseek"` |
| `model` | string | 是 | 具体模型 ID，如 `"doubao-vision-1.5-pro"` |
| `latency_ms` | integer | 是 | LLM 调用耗时（毫秒），不含图片落盘和 schema 校验 |

## 变更政策

| 变更类型 | 是否 Breaking | 处理 |
| --- | --- | --- |
| 新增**可选**顶层 / `hazards[]` 字段 | 否 | 前端忽略未知字段即可，但仍需同 PR 更新本文 |
| 新增**必填**字段 / 删除任何字段 / 改字段类型 | 是 | 需同 PR 改 Prompt + 后端 + 前端，并在 commit message 标注 `BREAKING:` |
| 调整枚举取值（如新增 `H11`） | 是 | 同上；需同步 `hazards.md` 与 Prompt 枚举字符串 |
| 调整字段长度 / 格式约束（如 `plain_warning` 上限改为 50 字） | 否 | 仅校验层需改 |

## 当前未在 schema 内的（v0.1 不做）

- 图片 URL / 缩略图 URL（MVP 图片仅服务端本地，不暴露给前端）
- 用户 ID / 工地 ID（无登录）
- 历史关联字段（`previous_inspection_id` 等）
- 评分 / 用户反馈字段（"这条隐患识别得对吗"）

这些将在 v0.2+ 引入时再扩展 schema。
