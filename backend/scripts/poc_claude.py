"""Phase 1 PoC 入口：单图调 Claude CLI Vision，打印原始响应 + 解析结果 + 成本/延迟。

用法（从 backend/ cwd）：
    python -m scripts.poc_claude tests/fixtures/images/case_001_stepladder_over_2_meters.jpg

依赖 backend/.env 中的：
    CLAUDE_CLI_PATH=claude
    CLAUDE_MODEL=sonnet
    CLAUDE_TIMEOUT_SECONDS=180
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

from app.llm.claude_cli import ClaudeCLIProvider
from app.llm.parser import parse_report

PROMPT_V1 = """你是一名资深建筑施工安全工程师。请仔细观察附带的工地照片（在你能看到的位置），
识别其中的安全隐患。

只返回 JSON 对象，不要附加任何解释、不要用 markdown 代码块包裹。

JSON 结构（字段含义见 docs/specs/report-schema.md）：
{
  "inspection_id": "00000000-0000-0000-0000-000000000000",
  "created_at": "2026-01-01T00:00:00Z",
  "plain_warning": "（1-30字口语化警示，任何工地角色秒懂）",
  "summary": "（面向安全员的一句话总结，含整体风险等级）",
  "overall_severity": "high | medium | low",
  "hazards": [
    {
      "category_code": "H1..H10 之一",
      "category_name": "对应中文名",
      "description": "看到的具体现象（专业用语）",
      "severity": "high | medium | low",
      "regulation": "引用规范条款，不确定时留空字符串",
      "suggestion": "可执行的整改建议"
    }
  ],
  "model_meta": {"provider": "claude_cli", "model": "placeholder", "latency_ms": 0}
}

类别枚举：
H1 高处坠落 | H2 物体打击 | H3 触电 | H4 坍塌 | H5 机械伤害 | H6 火灾 |
H7 中毒/窒息 | H8 起重伤害 | H9 个人防护缺失 | H10 其他/文明施工

约束：
- plain_warning 必须口语化、20 字内、任何工地角色（含工人）秒懂
- summary + hazards.description 用专业用语
- regulation 不允许编造，不确定就留空字符串
- 只用简体中文
"""


async def main(image_path: str) -> None:
    load_dotenv()
    provider = ClaudeCLIProvider(
        cli_path=os.environ.get("CLAUDE_CLI_PATH", "claude"),
        model=os.environ.get("CLAUDE_MODEL", "sonnet"),
        timeout_seconds=int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "120")),
    )
    image_bytes = Path(image_path).read_bytes()
    print(
        f"→ 调用 Claude ({provider.model_id})，图片 {len(image_bytes) / 1024:.1f} KB...",
        flush=True,
    )

    try:
        raw = await provider.analyze(image_bytes, PROMPT_V1)
    except Exception:
        print("!!! provider.analyze 抛异常：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    cost = raw.provider_payload.get("total_cost_usd", 0) or 0
    print(f"\n=== 原始响应 ({raw.latency_ms} ms, ${cost:.4f}) ===")
    print(raw.content)
    print()

    async def reprompt(corrective: str) -> str:
        r = await provider.analyze(image_bytes, corrective)
        return r.content

    try:
        report = await parse_report(raw.content, reprompt=reprompt)
    except Exception:
        print("!!! 解析失败：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print("=== 解析后的报告 ===")
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.poc_claude <image_path>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
