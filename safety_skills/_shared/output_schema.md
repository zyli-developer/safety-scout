---
skill_id: SHARED_OUTPUT
name: 输出格式规范
version: 1.1.0
load_strategy: always
---

# 输出格式规范

请严格按以下 JSON 结构输出报告，不要输出任何 JSON 之外的内容。

**示例的措辞长度即目标长度 —— 这是简洁性示范，不是花式扩写的起点。**

```json
{
  "report_meta": {
    "image_summary": "落地式脚手架外立面，工人绑扎钢筋",
    "scene_detected": ["S03", "S05", "S07"],
    "analysis_confidence": "高",
    "overall_risk_level": "重大"
  },

  "findings": [
    {
      "check_id": "B01",
      "category": "高坠风险",
      "status": "存在隐患",
      "title": "三层临边无栏杆",
      "location": "图片中部三层楼板边缘",
      "description": "三层东侧落差 6m，无防护栏",
      "severity": "重大",
      "regulation": "JGJ80-2016 4.1.1",
      "action": "立即停工，搭标准防护栏（上 1.2m+中 0.6m+挡脚板 ≥180mm）",
      "confidence": "高",
      "is_major": true,
      "major_basis": "建质规〔2024〕5号 第 6 条"
    }
  ],

  "no_findings": [
    { "check_id": "A01", "note": "工人均戴安全帽" },
    { "check_id": "C01", "note": "无配电箱" }
  ],

  "uncertain": [
    {
      "check_id": "S03-A03",
      "reason": "立杆垂直度需现场实测",
      "suggested_action": "用线锤复测"
    }
  ],

  "summary": {
    "total_checks": 95,
    "findings_count": 5,
    "fatal_count": 2,
    "major_count": 1,
    "minor_count": 2,
    "no_issue_count": 78,
    "uncertain_count": 12,
    "key_recommendations": [
      "立即停工整改 2 项重大隐患",
      "整改后安全员复验"
    ]
  }
}
```

## 字段说明（含**字数 budget**，超出会让报告变冗长难读）

| 字段 | 字数上限 | 写什么 |
|------|---------|--------|
| `image_summary` | ≤ 20 字 | 一句话场景 |
| `findings[].title` | ≤ 15 字 | 一句话定性 |
| `findings[].location` | ≤ 15 字 | 图片相对位置（如"画面中部"），便于人工复核 |
| `findings[].description` | **≤ 25 字** | **观察到的现象本身**，不要重复 action / regulation 内容 |
| `findings[].regulation` | **≤ 15 字** | **仅写规范代码 + 条号**（如 `JGJ80-2016 4.1.1`），**不展开条文文字** |
| `findings[].action` | ≤ 40 字 | 可执行整改动作；包含规格数值即可，不要描述验收流程 |
| `findings[].major_basis` | ≤ 20 字 | 仅写文号 + 条号（如 `建质规〔2024〕5号 第 6 条`），不展开 |
| `no_findings[].note` | **≤ 10 字** | 极简说明为什么不算（如"已戴安全帽" / "不适用"） |
| `uncertain[].reason` | ≤ 20 字 | 简述无法判断的原因 |
| `uncertain[].suggested_action` | ≤ 15 字 | 简述复核动作 |
| `summary.key_recommendations[]` | **最多 2 条**，每条 ≤ 20 字 | 顶层动作建议，不与单项 action 重复 |

枚举字段（直接选值，不要描述）：
- `status`：`存在隐患` / `不存在` / `无法判断`
- `severity`：`重大` / `较大` / `一般` / `低`
  - 重大：可能直接致伤亡，立即停工
  - 较大：违反强制条文，24h 内整改
  - 一般：违反非强制条款，限期整改
  - 低：文明施工类
- `confidence`：`高` / `中` / `低`

**`is_major` / `major_basis`**：是否命中《房屋市政工程生产安全重大事故隐患判定标准
（2024版）》建质规〔2024〕5号。判定规则与 `major_basis` 文本格式见
「重大事故隐患判定」shared 模块。**`severity=重大` 不是 `is_major=true` 的充分
条件 —— 二者独立判断**；不确信能否命中判定标准时，必须 `is_major=false` +
`major_basis=""`（空串，不要写"无"/"不适用"）。

## 输出约束

1. 只输出 JSON，不要任何前后缀文字、不要 markdown 代码块标记
2. `findings` 按 severity 从高到低排序
3. **严格遵守上述字数上限** —— 多写的字数对安全员价值低、对系统延迟有显著成本
4. **不允许编造条款号**：不确定规范条款时 `regulation=""`（空串）
5. **不要在 description 里复述 action 或 regulation 的内容**（三个字段各自独立）
6. JSON 必须可被 `json.loads()` 直接解析
