"""Phase 0 验证脚本：确认 claude-agent-sdk 能跑通本地 Claude Code 模型调用。

跑法：cd backend && uv run python scripts/verify_sdk.py

期望输出：能看到一段 AssistantMessage / TextBlock 文本，证明 SDK 通过 Claude CLI
成功调用了 claude-opus-4-7。失败时抛出 CLINotFoundError / ProcessError 等明确错误。
"""
from __future__ import annotations

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def main() -> None:
    options = ClaudeAgentOptions(model="claude-opus-4-7")
    async for msg in query(
        prompt="用 1 句中文回答：你是哪个模型？",
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
