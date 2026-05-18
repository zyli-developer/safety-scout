# Safety Scout · 工地安全隐患识别小程序

面向工地安全员的 AI 隐患识别工具：拍一张现场照片，由多模态 LLM 分析出潜在隐患，并给出专业、可执行的整改建议。

## 目标用户

工地安全员。强调：
- **流程极简**：理想路径只有「拍照 → 等待 → 看报告」三步。
- **结论专业**：输出要符合建筑施工安全规范用语，便于安全员直接转给班组整改。

## 技术栈

| 模块 | 选型 | 说明 |
| --- | --- | --- |
| 小程序前端 | [Taro](https://taro-docs.jd.com/) + React + TypeScript | 编译到微信小程序；后续可一码多端 |
| 后端 API | FastAPI (Python 3.11+) | 负责图片上传、调用 LLM、结果存储 |
| 多模态 LLM | DeepSeek / 豆包（Doubao） Vision，线上 API | 二选一或可切换，需具备图片识别能力 |
| 存储（待定） | 暂用本地 / 对象存储 OSS | 用于保存原图与分析记录 |

## 目录结构

```
safety-scout/
├── miniprogram/    # Taro 小程序工程
├── backend/        # FastAPI 后端服务
├── docs/           # 设计文档、Prompt、隐患规范资料
├── .gitignore
└── README.md
```

## 核心用户流程

1. 进入小程序首页 → 点「拍隐患」大按钮
2. 调起相机拍照（或从相册选）
3. 上传至后端 → 后端调用多模态 LLM
4. 展示结构化报告：隐患项、风险等级、依据条款、整改建议
5. 可保存 / 导出 / 转发

## 后续步骤

- [ ] 在 `docs/` 中确定隐患分类体系与 LLM Prompt 模版
- [ ] 初始化 `backend/` 的 FastAPI 工程骨架
- [ ] 初始化 `miniprogram/` 的 Taro 工程骨架
- [ ] 接入 DeepSeek / 豆包 Vision，跑通端到端 Demo
