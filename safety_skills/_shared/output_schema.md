---
skill_id: SHARED_OUTPUT
name: 输出格式规范
version: 1.0.0
load_strategy: always
---

# 输出格式规范

请严格按以下 JSON 结构输出报告，不要输出任何 JSON 之外的内容。

```json
{
  "report_meta": {
    "image_summary": "对图片整体场景的一句话描述（如：在建主体结构外侧，落地式脚手架，工人正在绑扎钢筋）",
    "scene_detected": ["S03", "S05", "S07"],
    "analysis_confidence": "高 / 中 / 低",
    "overall_risk_level": "重大 / 较大 / 一般 / 低"
  },

  "findings": [
    {
      "check_id": "B01",
      "category": "高坠风险",
      "status": "存在隐患",
      "title": "三层临边未设置防护栏杆",
      "location": "图片中部，三层楼板边缘，约画面 40% 高度位置",
      "description": "三层楼板东侧边缘（落差约 6m）未见任何防护栏杆，仅有 2 名工人在临边作业，存在高坠风险",
      "severity": "重大",
      "regulation": "JGJ80-2016 第 4.1.1 条：高度 2m 及以上的临边作业必须设置防护栏杆",
      "action": "立即停工，搭设标准防护栏杆（上杆 1.2m + 中杆 0.6m + 挡脚板 ≥180mm），栏杆完成验收后方可恢复作业",
      "confidence": "高",
      "is_major": true,
      "major_basis": "《房屋市政工程生产安全重大事故隐患判定标准（2024版）》建质规〔2024〕5号 第 6 条 高处作业 — 临边高度 ≥2m 无防护栏"
    }
  ],

  "no_findings": [
    {
      "check_id": "A01",
      "note": "图中可见 4 名工人均佩戴黄色安全帽"
    },
    {
      "check_id": "C01",
      "note": "图中未见配电箱（本场景不适用）"
    }
  ],

  "uncertain": [
    {
      "check_id": "S03-A03",
      "reason": "立杆垂直度需要现场测量，照片角度无法准确判断",
      "suggested_action": "建议现场用线锤复测"
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
      "整改完成后由安全员复验",
      "对作业班组进行专项安全交底"
    ]
  }
}
```

## 字段说明

- **check_id**：清单中的检查项编号（L1 用 A01-F06，场景清单用 S03-A01 形式）
- **status**：必须是 `存在隐患` / `不存在` / `无法判断` 三选一
- **severity**：重大 / 较大 / 一般 / 低 四档
  - **重大**：可能直接导致人员伤亡，必须立即停工
  - **较大**：违反强制性条文，需 24 小时内整改
  - **一般**：违反非强制性条款，限期整改
  - **低**：文明施工类问题，逐步改善
- **confidence**：你对该判断的把握度（高 / 中 / 低）
- **regulation**：必须引用具体规范编号 + 条款号
- **location**：必须用图片相对位置描述，便于人工复核
- **is_major** / **major_basis**：是否命中《房屋市政工程生产安全重大事故隐患判定标准
  （2024版）》建质规〔2024〕5号。判定规则与 `major_basis` 文本格式见
  「重大事故隐患判定」shared 模块。**`severity=重大` 不是 `is_major=true`
  的充分条件 —— 二者独立判断**；不确信能否命中判定标准时，
  必须 `is_major=false` + `major_basis=""`（空串，不要写"无"/"不适用"）。

## 输出约束

1. 只输出 JSON，不要任何前后缀文字、不要 markdown 代码块标记
2. `findings` 按 severity 从高到低排序
3. `no_findings` 列出所有未发现隐患的检查项，证明你检查过
4. `uncertain` 列出所有无法判断的项目和原因
5. JSON 必须可被 `json.loads()` 直接解析
