# 工地安全隐患识别 Skill 库

> 基于 Claude Agent SDK 的工地安全隐患视觉识别系统的知识库。
> 版本：1.0.0 | 最后更新：2026-05-21

## 目录结构

```
safety_skills/
├── _index.json                    # Skill 注册表（场景路由、元数据）
├── README.md                      # 本文件
│
├── _l1_core/                      # L1 通用必查项（每次都加载）
│   └── L1_必查清单.md             # 35 项核心必查
│
├── _shared/                       # 共享模块（每次都加载）
│   ├── role_definition.md         # 角色定义
│   ├── output_schema.md           # 输出格式规范
│   ├── fatal_warnings.md          # 致命隐患强化提示
│   └── cot_instructions.md        # 思维链分析流程
│
├── scenarios/                     # 场景清单（按需加载）
│   ├── S01_基坑工程.md
│   ├── S02_模板支撑.md
│   ├── S03_落地式脚手架.md
│   ├── S04_悬挑式脚手架.md
│   ├── S05_临边洞口与通道.md     ⚠️ 最重要
│   ├── S06_攀登悬空作业.md
│   ├── S07_施工用电.md
│   ├── S08_起重机械.md
│   ├── S09_中小型机械.md
│   ├── S10_文明施工.md
│   ├── S11_消防安全.md
│   └── S12_人员行为.md
│
└── _integration/                  # 集成代码示例
    ├── agent_integration.py       # Claude Agent SDK 集成示例
    ├── skill_loader.py            # Skill 加载器
    └── prompt_builder.py          # 提示词组装器
```

## 工作流程

```
[用户拍照] → [Agent 启动]
                ↓
        [加载 L1 + Shared 到 system prompt]
                ↓
        [图片分析：场景识别（Step 1-2）]
                ↓
        [Agent 调用 load_scenario_skill tool]
                ↓
        [加载命中场景的 L2 清单到 context]
                ↓
        [逐项核查（Step 3）]
                ↓
        [自我审查（Step 4）]
                ↓
        [输出 JSON 报告（Step 5）]
```

## 核心设计原则

### 1. 双层清单结构

- **L1 必查**（35 项）：每次都加载，保证基础召回率
- **L2 场景**（共约 200 项，分 12 个场景）：按需加载，避免提示词膨胀

### 2. Agent 主动加载

Agent SDK 启动时，将 L1 + Shared 写入 system prompt。
分析过程中，Agent 通过 `load_scenario_skill` tool 自主加载需要的 L2 清单。
这是真正的 agentic 工作流。

### 3. 强制结构化输出

所有报告必须按 `output_schema.md` 输出 JSON，便于下游处理。

### 4. 致命项强化

致命 7 类隐患单独提示，要求"宁可误报，不可漏报"。

### 5. 可溯源

每条隐患必须附带规范条款编号，便于复核。

## 维护说明

### 新增场景
1. 在 `scenarios/` 下创建 `S13_xxx.md`
2. 按 frontmatter + 标准结构编写
3. 在 `_index.json` 中注册

### 修改清单
直接编辑对应的 `.md` 文件，提升 `version` 号。

### 规范更新
1. 更新 `_shared/role_definition.md` 中的规范列表
2. 更新对应清单中的 `regulation` 字段
3. 在 commit message 中注明规范版本变更

## 已知限制

1. **测量类项目**：模型无法准确测量距离、角度、垂直度等。这些项标注为"建议现场实测"。
2. **隐蔽工程**：墙体内、地下、看不见的部位无法判断。
3. **资质类**：人员证件、检测报告等纸质资料类的检查项无法判断。

## 后续路线图

- [ ] 接入目标检测模型做预处理（Detection-then-Reasoning）
- [ ] 把清单条目改造为 RAG 知识库（细粒度 chunk）
- [ ] 引入地方标准、企业标准
- [ ] 支持视频帧序列分析
- [ ] 支持多张照片联合分析（同一作业面的多角度）
