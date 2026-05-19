"""录制 LLM 响应到 `tests/fixtures/llm/`，供集成测试重放。

用法（从 backend/ cwd）：
    python -m scripts.replay_capture
    python -m scripts.replay_capture --prompt-version v2

行为：
- 扫 `backend/tests/fixtures/images/*.jpg`
- 每张图调一次真实 ClaudeCLIProvider.analyze
- 写 `backend/tests/fixtures/llm/{image_stem}.json`（架构 design §5.2 格式）

CAUTION：会真打 Claude CLI、产生 token cost。Prompt 改一次跑一次。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

from app.llm.claude_cli import ClaudeCLIProvider
from app.llm.prompt import ANALYZE_PROMPT

# 相对 backend/ 根的两个 fixture 目录。
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "images"
FIXTURES_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "llm"


async def _capture_one(
    provider: ClaudeCLIProvider,
    image_path: Path,
    prompt_version: str,
) -> Path:
    image = image_path.read_bytes()
    digest = sha256(image).hexdigest()
    print(
        f"-> 录制 {image_path.name} "
        f"({len(image) / 1024:.1f} KB, sha {digest[:8]}) ...",
        flush=True,
    )

    raw = await provider.analyze(image, ANALYZE_PROMPT)

    # 路径用 POSIX 风格存进 fixture（跨平台一致；Path.as_posix 在 Windows 上把 \ 转 /）。
    image_rel = image_path.relative_to(_BACKEND_ROOT).as_posix()
    fixture: dict[str, object] = {
        "input": {
            "image_sha256": digest,
            "image_path": image_rel,
            "prompt_version": prompt_version,
            "provider": "claude_cli",
        },
        "output": {
            "content": raw.content,
            "model": raw.model,
            "latency_ms": raw.latency_ms,
            "provider_payload": raw.provider_payload,
        },
        "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "captured_by": "scripts/replay_capture.py",
    }

    out_path = FIXTURES_DIR / f"{image_path.stem}.json"
    out_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   OK 写入 {out_path.relative_to(_BACKEND_ROOT).as_posix()}", flush=True)
    return out_path


async def main(prompt_version: str) -> None:
    load_dotenv()
    provider = ClaudeCLIProvider(
        cli_path=os.environ.get("CLAUDE_CLI_PATH", "claude"),
        model=os.environ.get("CLAUDE_MODEL", "sonnet"),
        timeout_seconds=int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "180")),
    )
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(IMAGES_DIR.glob("*.jpg"))
    if not images:
        print(f"!!! 没找到任何图片：{IMAGES_DIR}", file=sys.stderr)
        sys.exit(1)

    for image_path in images:
        await _capture_one(provider, image_path, prompt_version)

    print(f"\n全部完成：{len(images)} 张图已录到 {FIXTURES_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt-version",
        default="v1",
        help="写到 fixture.input.prompt_version 的版本标签（默认 v1）",
    )
    args = parser.parse_args()
    asyncio.run(main(args.prompt_version))
