# 架构设计草案

> 第一版仅记录达成共识的要点，便于后续 PR 时对照。具体接口、字段会在工程骨架建好后再细化。

## 1. 整体数据流

```
[微信小程序 · Taro]
      │  ① 拍照 / 选图
      ▼
[小程序前端]
      │  ② POST /api/v1/inspections  (multipart: image)
      ▼
[FastAPI 后端]
      │  ③ 保存原图（本地 / OSS）
      │  ④ 组装 Prompt + 图片，调用多模态 LLM
      ▼
[DeepSeek / 豆包 Vision API]
      │  ⑤ 返回结构化 JSON（隐患列表）
      ▼
[FastAPI 后端]
      │  ⑥ 校验 / 规范化 / 落库
      ▼
[小程序前端]
      │  ⑦ 渲染隐患报告，可保存 / 导出
```

## 2. 关键设计点

### 2.1 LLM 抽象层
后端用一个 `llm_provider` 接口，封装 DeepSeek 与 Doubao 两家 Vision API，便于切换 / A-B 对比。

### 2.2 结构化输出
Prompt 强制 LLM 返回 JSON，字段建议：
```json
{
  "summary": "整体风险等级与一句话总结",
  "hazards": [
    {
      "category": "高处作业 / 用电 / 消防 / 临边洞口 / ...",
      "description": "看到的具体现象",
      "severity": "high | medium | low",
      "regulation": "引用的规范条款（若有）",
      "suggestion": "给安全员的整改建议（动作可执行）"
    }
  ]
}
```
若 LLM 输出不合法 JSON，后端做一次容错（regex 抽取 / 二次纠正提示）。

### 2.3 流程极简
- 首页只有一个「拍隐患」主按钮，不强制登录。
- 上传中给出明确的进度反馈（拍照成功 → AI 分析中 → 报告就绪）。
- 报告页一屏可见，按严重等级排序，颜色区分。

## 3. 待决定（TODO）

- [ ] DeepSeek vs 豆包：先接入哪家，价格与 QPS 限制
- [ ] 图片存储：本地落盘还是接 OSS（阿里云 / 腾讯云）
- [ ] 是否需要登录态 / 工地项目维度的归档
- [ ] 隐患分类体系：自定义 or 参考住建部规范
- [ ] 历史记录与导出（PDF / 图文）
