"""Judge rubric —— LLM-as-Judge 的评判 prompt（独立模块，便于版本化）。

修改 rubric 必须同 PR 改 `JUDGE_RUBRIC_VERSION`（quality_judgments.judge_rubric_version
列以此 group_by；不变版本号会污染历史 verdict 的可比性）。

v1.0：4 维度 pairwise + 盲评 + 强制 JSON 输出（docs/specs/quality-tracking.md §4.2）
"""

from __future__ import annotations

JUDGE_RUBRIC_VERSION = "1.0"

JUDGE_RUBRIC = """你是一名资深建筑安全总监。下面给你 1 张工地照片 + 两份独立的安全分析报告（A 和 B）。
请独立比较以下 4 个维度，每维度选 winner（A / B / tie）+ 一句话理由：

1. recall —— 谁识别出更多真实存在的隐患（漏报谁少）？
2. precision —— 谁的识别更少误判（描述了图中实际没有的隐患）？
3. regulation_quality —— 谁引用的规范条款更具体、更可信、不编造？
4. action_actionability —— 谁的整改建议更具体、动作可直接落地？

最后给 overall winner + 一句话总结 + 你的 confidence。

约束（违反任一条都会损害判定可信度）：
- 你**不知道** A / B 哪个是新版本 —— 别推测，只看实际内容
- 若两份基本等价，**大方给 tie**，不要为决断而决断
- 不要受 finding 数量绝对值吸引 —— 多不等于好，质量更重要
- regulation_quality 重点考察"不编造条款号" —— 宁缺勿造的引用比看起来很详细
  但是编造的好
- 不要在你的输出里出现 A/B 的具体 finding 数量等显式偏好信号，只评判优劣

返回 JSON（**只**返 JSON，无前后缀，无 markdown 包裹）：
{
  "by_dimension": {
    "recall":              {"winner":"A|B|tie", "reason":"..."},
    "precision":           {"winner":"A|B|tie", "reason":"..."},
    "regulation_quality":  {"winner":"A|B|tie", "reason":"..."},
    "action_actionability":{"winner":"A|B|tie", "reason":"..."}
  },
  "overall": {"winner":"A|B|tie", "summary":"...", "confidence":"high|medium|low"}
}
"""


def render_judge_prompt(report_a_json: str, report_b_json: str) -> str:
    """把 rubric + 两份 report JSON 拼成完整 judge prompt。

    Args:
        report_a_json: A 报告的 model_dump_json() 输出
        report_b_json: B 报告的 model_dump_json() 输出

    Returns:
        完整 prompt 字符串，可直接喂给 LLM provider.analyze()
    """
    return (
        f"{JUDGE_RUBRIC}\n\n"
        f"=== 报告 A ===\n```json\n{report_a_json}\n```\n\n"
        f"=== 报告 B ===\n```json\n{report_b_json}\n```\n"
    )
