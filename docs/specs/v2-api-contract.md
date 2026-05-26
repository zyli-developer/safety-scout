# v2 API 合同（前端/集成方对照用）

> 与 v1 并存，路径独立。v1 数据**不**自动迁移到 v2（dev 阶段无生产数据约束）。
> 字段权威源：`backend/app/schemas/report_v2.py` + `safety_skills/_shared/output_schema.md`。

## 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v2/analyze` | POST multipart | 上传图片，返回 202 + `inspection_id` + `poll_url` |
| `/api/v2/inspections/{id}` | GET | 轮询状态；succeeded 时返完整 `ReportV2Payload` |

POST 限速 10/min/IP（与 v1 共用 slowapi）。GET 不限速。
v2 单图分析 30-60s，前端 `poll_interval_ms=2000`、`timeout_ms ≥ 120s`。

## v1 → v2 schema 差异（关键字段）

| 维度 | v1 (`ReportPayload`) | v2 (`ReportV2Payload`) |
|---|---|---|
| 顶层结构 | `summary` + `hazards[]` + `model_meta` | `report_meta` + `findings[]` + `no_findings[]` + `uncertain[]` + `summary` |
| 隐患严重度 | `high / medium / low` | **`重大 / 较大 / 一般 / 低`**（中文，对齐住建部规范用语） |
| 隐患编号 | `category_code`（H1/E2/...） | `check_id`（L1=A01..F06，L2=`S03-A01`...） |
| 整图描述 | 无 | `report_meta.image_summary` |
| 命中场景 | 无 | `report_meta.scene_detected: ["S03","S05",...]` |
| 模型把握度 | 无 | 每条 `finding.confidence: 高/中/低` |
| 图片位置 | 无 | 每条 `finding.location`（图片相对位置） |
| 已核查无隐患项 | 无 | `no_findings[]`（防"漏检装作不存在"） |
| 无法判断项 | 无 | `uncertain[{check_id,reason,suggested_action}]` |
| 整体风险等级 | 无 | `report_meta.overall_risk_level: 重大/较大/一般/低` |

## v2 GET 响应示例（succeeded）

```json
{
  "inspection_id": "...",
  "status": "succeeded",
  "created_at": "2026-05-21T...Z",
  "updated_at": "2026-05-21T...Z",
  "error": null,
  "report": {
    "report_meta": {
      "image_summary": "...",
      "scene_detected": ["S03", "S05"],
      "analysis_confidence": "高",
      "overall_risk_level": "重大"
    },
    "findings": [
      {
        "check_id": "B01",
        "category": "高坠风险",
        "status": "存在隐患",
        "title": "三层临边未设置防护栏杆",
        "location": "图片中部，三层楼板边缘",
        "description": "...",
        "severity": "重大",
        "regulation": "JGJ80-2016 第 4.1.1 条",
        "action": "立即停工，搭设标准防护栏杆",
        "confidence": "高"
      }
    ],
    "no_findings": [{"check_id": "A01", "note": "..."}],
    "uncertain": [{"check_id": "S03-A03", "reason": "...", "suggested_action": "..."}],
    "summary": {
      "total_checks": 95,
      "findings_count": 5,
      "fatal_count": 2,
      "major_count": 1,
      "minor_count": 2,
      "no_issue_count": 78,
      "uncertain_count": 12,
      "key_recommendations": ["立即停工整改 2 项重大隐患"]
    }
  }
}
```

## 前端渲染要点（建议）

- `findings` **后端已按 severity 从高到低排序**（output_schema.md §输出约束），渲染时按数组顺序即可
- `severity` 颜色映射建议：重大=红、较大=橙、一般=黄、低=灰
- `regulation` 字段非空时高亮显示，提升专业度
- `no_findings` 默认折叠（"已检查通过 N 项"），点击展开列表
- `uncertain` 单独区块显示"建议现场复核"
- `report_meta.overall_risk_level` 顶部 banner 体现

## 错误响应

`failed` 状态下 `error` 字段非空，envelope 与 v1 一致：

```json
{"error": {"code": "LLM_CALL_FAILED|LLM_TIMEOUT|INTERNAL", "message": "...", "user_message": "..."}}
```

`code=LLM_CALL_FAILED` + `message` 包含 "submit_safety_report" 是 Agent 没完成 submit 流程的特征（plan §5.1 风险表 "Agent 死循环"）。

## 后端 metric 埋点（运维/监控）

`logger=app.safety_agent.tools` 上的 `extra.metric` 字段：

| metric | level | 含义 |
|---|---|---|
| `v2.tool.load_scenario.hit` | INFO | 场景命中 + 携带 scenario_id/name |
| `v2.tool.load_scenario.unknown_id` | WARN | Agent 写错场景 ID（多发可能是 prompt 不够清楚） |
| `v2.tool.submit.json_error` | WARN | Agent 输出非合法 JSON |
| `v2.tool.submit.schema_error` | WARN | JSON 合法但 schema 不过；携带 first_loc |
| `v2.tool.submit.accepted` | INFO | 报告通过；携带 severity_distribution + scene_detected |
| `v2.tool.submit.empty` | WARN | 工具被空 payload 调用 |

`logger=app.services.inspection_v2` 在 succeeded 时输出 `latency_ms / tool_calls / scenarios / findings / input_tokens / output_tokens / cost_usd`。
