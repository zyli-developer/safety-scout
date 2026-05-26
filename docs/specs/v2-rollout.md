# v2 灰度上线 + Skill 维护 + Badcase 闭环

> 改造计划 §五 + §六 验收项之三。
> 部署细节见 `v2-deployment.md`；API/schema 合同见 `v2-api-contract.md`。

## 一、灰度上线策略（plan §5.2）

v1 路径（`POST /api/v1/inspections`）与 v2 路径（`POST /api/v2/analyze`）**已并存**，
无需后端代码改动。流量分配在**前端**（miniprogram / 桌面 H5）层做：

### 切流开关（前端实现，本仓库尚未加）

在 `miniprogram/src/config.ts` 添加一个 ramp 比例：

```ts
// 0.0 ~ 1.0，决定多少比例的请求走 v2
// 配合远程配置中心（如有）动态下发；MVP 阶段直接改这个常量重新打包
export const V2_TRAFFIC_SHARE = 0.10;
```

在 `miniprogram/src/api/inspections.ts` 的 `createInspection` 里：
```ts
const useV2 = Math.random() < V2_TRAFFIC_SHARE;
const endpoint = useV2 ? '/api/v2/analyze' : '/api/v1/inspections';
// poll_url 由后端返回，前端只要按 url 轮询，不需要关心版本
```

报告渲染层按 `report` 字段结构判断 v1（`hazards[]`）vs v2（`findings[]/no_findings[]/uncertain[]`），
或者用响应里的 `poll_url` 反推（v2 的 url 以 `/api/v2/` 开头）。

### 切流节奏（plan §5.2，操作侧）

| 阶段 | V2_TRAFFIC_SHARE | 观察期 | 通过条件 |
|---|---|---|---|
| 内部试用 | 1.0（仅内部账号） | 1 周 | 安全员/项目经理用真实图试用，badcase < 10/天 |
| 灰度 10% | 0.10 | 1-2 天 | 错误率（status='failed'）≤ v1；P95 latency ≤ 6min |
| 灰度 50% | 0.50 | 3-5 天 | 同上 + 用户主观满意度无明显回退 |
| 全量 | 1.0 | 持续 | v1 继续保留作为 fallback 30 天，不下线 |

### 灰度期监控关注点

- **错误率**：v1 vs v2 status='failed' 占比；v2 主要错误源是 `LLM_CALL_FAILED`（agent 没调 submit）和 `LLM_TIMEOUT`
- **耗时分布**：v2 P50/P95（实测 case_001 ~230s，预期 P95 在 5min 内；超过要查 rate limit）
- **token / cost**：`v2.tool.submit.accepted` 日志的 input_tokens/output_tokens；订阅额度 5h 窗口要预留
- **schema 校验失败率**：`v2.tool.submit.schema_error` 计数 / 总 `submit.accepted` 计数 < 5% 是健康的（Agent 偶尔会瞎填）
- **场景命中分布**：`v2.tool.load_scenario.hit` 按 scenario_id 聚合，看哪些场景频繁出现（指导后续 L2 清单优化）

回退预案：把 `V2_TRAFFIC_SHARE` 改回 0、重新打包小程序即可。后端 v1 路径不会受 v2 影响。

## 二、Badcase 闭环（plan §5.3）

### 设计原则

不在后端实现"误报/漏报"标注 API（YAGNI），先用现有数据建反馈链：

1. **被动数据**：v2 的 `uncertain[]` 列表本身就是模型自报"不确定"的项，是天然的 badcase 候选源
2. **主动数据**：前端报告页面加"反馈"按钮（feat/pc-web-ui 范围），数据走 v1 已有的某个 endpoint 或单独写

### 反馈数据收集（建议方案，待实施）

最小落地方式：
- 前端在报告页加"误报 / 漏报 / 整改建议不可执行"三类标记按钮
- 请求 `POST /api/v2/inspections/{id}/feedback`（**本仓库尚未实现**），body：
  ```json
  {
    "kind": "false_positive | missed | bad_action",
    "check_id": "B01",     // 误报/不可执行时必填；漏报时可空
    "description": "工人其实戴了安全带，模型没看到"
  }
  ```
- 后端落 `feedbacks` 表（schema 待 design）；不直接修改 inspections 表

### 聚合 → Skill 改进闭环

每月（或每 1000 个反馈）跑一次聚合：
```sql
SELECT check_id, kind, COUNT(*) AS n
FROM feedbacks
WHERE created_at >= ?
GROUP BY check_id, kind
ORDER BY n DESC;
```

按高频 check_id 反查所属 L1/L2 清单：
- `check_id` 以 `A01..F06` 开头 → `safety_skills/_l1_core/L1_必查清单.md`
- `check_id` 以 `S03-A01` 这样开头 → `safety_skills/scenarios/S03_*.md`

由**安全工程师**（不是开发）编辑对应 markdown 文件的"判定要点"段落，把易混淆的特征 / 排除条件写清楚。
**禁止改 check_id 编号**（前端 / 旧反馈数据会断裂）。

### 重新部署（无需改代码）

```bash
git pull   # 拿到 markdown 改动
# 重启 backend；SkillLoader 在进程启动时 preload，运行期不会自动重载
sudo systemctl restart safety-scout-backend
```

如果想热重载（避免重启），需要给 `get_skill_loader` 工厂加 TTL 或显式 invalidation —— 当前 `@lru_cache(maxsize=1)` 永久缓存，不适合频繁改 skill 的场景。这是已知 follow-up。

## 三、Skill 维护手册（plan §六，给安全工程师）

### 文件位置

```
safety_skills/
├── _index.json              # 场景注册表（改动需开发同步）
├── _l1_core/
│   └── L1_必查清单.md       # 35 项必查项；每次分析都查
├── _shared/                 # 通用模块，每次都注入 system prompt
│   ├── role_definition.md
│   ├── cot_instructions.md
│   ├── fatal_warnings.md
│   └── output_schema.md
└── scenarios/
    └── S03_落地式脚手架.md  # L2，命中场景时按需加载
```

### 改一条已有的判定要点（最常见）

1. 打开对应 `.md` 文件
2. 找到对应 `check_id` 段落（如 `## B01 三层临边未设置防护栏杆`）
3. 修改"判定要点 / Diagnostic"小节文字 —— 这部分模型读得最仔细，加排除条件 / 区分细节最有效
4. 不要改 frontmatter（顶部 `---` 包裹的 yaml 元数据）和 `check_id` 编号
5. 在 frontmatter 里 bump `version` 字段（如 `1.0.0` → `1.0.1`）

### 加一个新场景

1. 在 `safety_skills/scenarios/` 新建 `S13_xxx.md`，按现有 S01-S12 的 frontmatter + 章节结构写
2. 在 `_index.json` 注册：
   ```json
   {
     "id": "S13",
     "name": "新场景名",
     "file": "scenarios/S13_xxx.md",
     "trigger_features": ["关键词1", "关键词2"],
     "estimated_tokens": 1500,
     "priority": "中"
   }
   ```
3. 跑 `uv run pytest backend/tests/unit/test_safety_agent_loader.py -q` 确保新场景能加载
4. 跑 smoke 看 prompt builder 输出长度：`uv run pytest backend/tests/unit/test_safety_agent_prompt.py::test_system_prompt_length_in_range -q`（≤ 16000 字符）

### 不能做的事

- ❌ 改 `check_id` 编号 —— 会破坏反馈数据回溯
- ❌ 删 frontmatter —— loader 用 frontmatter 探测元数据
- ❌ 改 `_shared/output_schema.md` —— 这是后端 `ReportV2Payload` 的合同；改了后端代码必须同步改 schema
- ❌ 修改 `_integration/*.py` —— 那是参考代码，已被 `backend/app/safety_agent/` 重写
