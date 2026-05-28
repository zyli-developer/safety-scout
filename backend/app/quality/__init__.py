"""Quality tracking · Layer 2 评判层（LLM-as-Judge pairwise + 位置去偏）。

模块边界（docs/specs/quality-tracking.md §4）：
- judge_rubric: rubric prompt 文本 + 版本号
- judge_service: pairwise judge + 位置去偏 workflow
- judgments_repo: quality_judgments 表 CRUD

调用关系：
    scripts/judge_versions.py
        ↓
    judge_service.judge_pair(baseline_report, candidate_report, image)
        ↓ x2 (swap A/B)
    _single_judge(rubric, A=..., B=...) → LLM (Claude SDK)
        ↓
    judgments_repo.record(verdict)
"""
