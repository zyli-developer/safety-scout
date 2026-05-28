"""LLM-as-Judge pairwise 评判服务 —— 位置去偏 workflow（doc §4.4）。

核心 API：`judge_pair(...)` 跑 2 次 judge（A/B swap），仅 overall winner 一致时
算 `confident=True`，否则标 `inconclusive`。

判定模型 ≠ 被测模型 —— 防 self-preference bias（doc §4.3）。

依赖反转：service 不直接 import provider，而是接受一个 `judge_call` 协议（
async fn: str → str），由调用方注入。这样：
- 真实 judge 用 ClaudeCLIProvider/DoubaoProvider 包一层 closure
- 单测里塞 stub fn 即可，不需要 mock 整个 provider
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from app.quality.judge_rubric import (
    JUDGE_RUBRIC_VERSION,
    render_judge_prompt,
)

logger = logging.getLogger(__name__)

# judge_call: 接受完整 prompt，返回 LLM 的原始字符串响应（应该是 JSON）。
# 用 closure 注入而非 import provider 是为了：
# 1. 单测不需要 mock provider 类
# 2. 真实使用时可以同一函数对接 Claude/Doubao/OpenAI 任意 provider
JudgeCallable = Callable[[str], Awaitable[str]]

Winner = Literal["A", "B", "tie"]
Confidence = Literal["high", "medium", "low"]
# 内部归一化后的 winner —— A/B 翻译成 baseline/candidate
NormWinner = Literal["baseline", "candidate", "tie"]


@dataclass(frozen=True)
class DimensionVerdict:
    winner: Winner
    reason: str


@dataclass(frozen=True)
class SingleJudgeResult:
    """一次 judge 调用的解析结果（未做位置归一化）。"""

    by_dimension: dict[str, DimensionVerdict]
    overall_winner: Winner
    overall_summary: str
    confidence: Confidence
    raw_json: str  # 原始 judge 返回


@dataclass(frozen=True)
class PairVerdict:
    """位置去偏后的最终 verdict（一对 baseline/candidate 的判定结果）。

    `confident=False` 时其余字段除 raw_json_1/raw_json_2 都不可靠，调用方应当
    按 inconclusive 处理。
    """

    id: str
    baseline_inspection_id: str | None  # CLI 模式可能无 inspection_id，此时为 None
    candidate_inspection_id: str | None
    judge_model: str
    judge_rubric_version: str
    confident: bool
    # 以下字段在 confident=True 时有效
    winner_overall: NormWinner | None
    winner_recall: NormWinner | None
    winner_precision: NormWinner | None
    winner_regulation: NormWinner | None
    winner_action: NormWinner | None
    confidence_self: Confidence | None
    overall_summary: str | None
    # 原始 judge 返回（两次）+ 成本
    raw_json_1: str
    raw_json_2: str
    cost_usd: float = 0.0


# === JSON 解析 ===


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _strip_json(raw: str) -> str:
    """从 judge 原始响应里提取 JSON 体 —— 若模型不听话用了 markdown 包裹也能救。"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    # 容错：如果 LLM 在前后加了解释文字，抠出第一个 { ... } 块
    if not raw.startswith("{"):
        m = _JSON_BLOCK.search(raw)
        if m:
            raw = m.group(0)
    return raw


class JudgeParseError(ValueError):
    """Judge 返回不可解析或不符合 schema。"""


def parse_judge_response(raw: str) -> SingleJudgeResult:
    """解析单次 judge 调用的原始响应 → SingleJudgeResult。

    解析失败抛 JudgeParseError —— 上层把这次 judge 标记为失败，记录但不进统计。
    """
    try:
        data = json.loads(_strip_json(raw))
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"judge JSON 解析失败: {exc.msg}") from exc

    if not isinstance(data, dict) or "by_dimension" not in data or "overall" not in data:
        raise JudgeParseError(f"judge 响应缺 by_dimension / overall 字段: {data}")

    dims_raw = data["by_dimension"]
    expected = ("recall", "precision", "regulation_quality", "action_actionability")
    dims: dict[str, DimensionVerdict] = {}
    for k in expected:
        if k not in dims_raw or not isinstance(dims_raw[k], dict):
            raise JudgeParseError(f"by_dimension 缺 {k}")
        w = dims_raw[k].get("winner")
        if w not in ("A", "B", "tie"):
            raise JudgeParseError(f"by_dimension.{k}.winner 非法: {w}")
        dims[k] = DimensionVerdict(
            winner=w,  # type: ignore[arg-type]
            reason=str(dims_raw[k].get("reason", "")),
        )

    overall = data["overall"]
    ow = overall.get("winner")
    if ow not in ("A", "B", "tie"):
        raise JudgeParseError(f"overall.winner 非法: {ow}")
    conf = overall.get("confidence", "medium")
    if conf not in ("high", "medium", "low"):
        raise JudgeParseError(f"overall.confidence 非法: {conf}")

    return SingleJudgeResult(
        by_dimension=dims,
        overall_winner=ow,  # type: ignore[arg-type]
        overall_summary=str(overall.get("summary", "")),
        confidence=conf,  # type: ignore[arg-type]
        raw_json=raw,
    )


# === 位置去偏 ===


_FLIP = {"A": "B", "B": "A", "tie": "tie"}


def _flip_winner(w: Winner) -> Winner:
    return _FLIP[w]  # type: ignore[return-value]


def _normalize_to_baseline_candidate(
    judge_winner: Winner, swap_position: int
) -> NormWinner:
    """把 A/B winner 翻译成 baseline/candidate 视角。

    swap_position=0: A=baseline, B=candidate → A→baseline, B→candidate
    swap_position=1: A=candidate, B=baseline → A→candidate, B→baseline
    """
    if judge_winner == "tie":
        return "tie"
    if swap_position == 0:
        return "baseline" if judge_winner == "A" else "candidate"
    return "candidate" if judge_winner == "A" else "baseline"


def _verdicts_agree(
    j1: SingleJudgeResult, j2_normalized_overall: NormWinner, j1_normalized_overall: NormWinner
) -> bool:
    """overall winner 在 baseline/candidate 视角下一致 → judge 不受位置影响 → 可信。"""
    return j1_normalized_overall == j2_normalized_overall


# === 主入口 ===


async def judge_pair(
    *,
    judge_call: JudgeCallable,
    judge_model: str,
    baseline_report_json: str,
    candidate_report_json: str,
    baseline_inspection_id: str | None = None,
    candidate_inspection_id: str | None = None,
    cost_per_call_usd: float = 0.0,
) -> PairVerdict:
    """对一对 (baseline, candidate) 报告做 pairwise judge + 位置去偏。

    Args:
        judge_call: async fn(prompt) → str，由调用方注入（包 LLM provider）
        judge_model: 用于落库的 judge model 标识，不影响调用本身
        baseline_report_json: baseline 报告的 JSON 字符串
        candidate_report_json: candidate 报告的 JSON 字符串
        baseline_inspection_id / candidate_inspection_id: 可选，落库 join 用
        cost_per_call_usd: 每次 judge 成本估算（外部传入；judge_call 通常不返成本）

    Returns:
        PairVerdict —— `confident=True` 时各 winner_* 字段有效；
        `confident=False` 表示位置敏感 / 解析失败，应作为 inconclusive 处理。
    """
    # 第 1 次：A=baseline, B=candidate
    prompt_1 = render_judge_prompt(baseline_report_json, candidate_report_json)
    raw_1 = await judge_call(prompt_1)

    # 第 2 次：A=candidate, B=baseline （swap）
    prompt_2 = render_judge_prompt(candidate_report_json, baseline_report_json)
    raw_2 = await judge_call(prompt_2)

    try:
        j1 = parse_judge_response(raw_1)
        j2 = parse_judge_response(raw_2)
    except JudgeParseError as exc:
        logger.warning(
            "judge response parse failed",
            extra={
                "metric": "judge.parse_failed",
                "judge_model": judge_model,
                "err": str(exc),
            },
        )
        return PairVerdict(
            id=str(uuid.uuid4()),
            baseline_inspection_id=baseline_inspection_id,
            candidate_inspection_id=candidate_inspection_id,
            judge_model=judge_model,
            judge_rubric_version=JUDGE_RUBRIC_VERSION,
            confident=False,
            winner_overall=None,
            winner_recall=None,
            winner_precision=None,
            winner_regulation=None,
            winner_action=None,
            confidence_self=None,
            overall_summary=None,
            raw_json_1=raw_1,
            raw_json_2=raw_2,
            cost_usd=cost_per_call_usd * 2,
        )

    # 归一化两次 overall winner
    j1_overall_norm = _normalize_to_baseline_candidate(j1.overall_winner, swap_position=0)
    j2_overall_norm = _normalize_to_baseline_candidate(j2.overall_winner, swap_position=1)

    if not _verdicts_agree(j1, j2_overall_norm, j1_overall_norm):
        # 位置敏感 → 不可信，标 inconclusive（doc §4.4）
        logger.info(
            "judge inconclusive (position-sensitive)",
            extra={
                "metric": "judge.inconclusive",
                "j1_overall": j1.overall_winner,
                "j2_overall": j2.overall_winner,
            },
        )
        return PairVerdict(
            id=str(uuid.uuid4()),
            baseline_inspection_id=baseline_inspection_id,
            candidate_inspection_id=candidate_inspection_id,
            judge_model=judge_model,
            judge_rubric_version=JUDGE_RUBRIC_VERSION,
            confident=False,
            winner_overall=None,
            winner_recall=None,
            winner_precision=None,
            winner_regulation=None,
            winner_action=None,
            confidence_self=None,
            overall_summary=None,
            raw_json_1=raw_1,
            raw_json_2=raw_2,
            cost_usd=cost_per_call_usd * 2,
        )

    # 高置信 verdict —— 取 j1 的细节（j2 仅用于交叉验证 overall）
    return PairVerdict(
        id=str(uuid.uuid4()),
        baseline_inspection_id=baseline_inspection_id,
        candidate_inspection_id=candidate_inspection_id,
        judge_model=judge_model,
        judge_rubric_version=JUDGE_RUBRIC_VERSION,
        confident=True,
        winner_overall=j1_overall_norm,
        winner_recall=_normalize_to_baseline_candidate(
            j1.by_dimension["recall"].winner, swap_position=0
        ),
        winner_precision=_normalize_to_baseline_candidate(
            j1.by_dimension["precision"].winner, swap_position=0
        ),
        winner_regulation=_normalize_to_baseline_candidate(
            j1.by_dimension["regulation_quality"].winner, swap_position=0
        ),
        winner_action=_normalize_to_baseline_candidate(
            j1.by_dimension["action_actionability"].winner, swap_position=0
        ),
        confidence_self=j1.confidence,
        overall_summary=j1.overall_summary,
        raw_json_1=raw_1,
        raw_json_2=raw_2,
        cost_usd=cost_per_call_usd * 2,
    )
