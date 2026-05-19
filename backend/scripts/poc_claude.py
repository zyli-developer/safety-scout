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
from app.llm.prompt import ANALYZE_PROMPT


async def main(image_path: str) -> None:
    load_dotenv()
    provider = ClaudeCLIProvider(
        cli_path=os.environ.get("CLAUDE_CLI_PATH", "claude"),
        model=os.environ.get("CLAUDE_MODEL", "sonnet"),
        timeout_seconds=int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "180")),
    )
    image_bytes = Path(image_path).read_bytes()
    print(
        f"→ 调用 Claude ({provider.model_id})，图片 {len(image_bytes) / 1024:.1f} KB...",
        flush=True,
    )

    try:
        raw = await provider.analyze(image_bytes, ANALYZE_PROMPT)
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
