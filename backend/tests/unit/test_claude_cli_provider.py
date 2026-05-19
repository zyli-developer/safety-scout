"""ClaudeCLIProvider 行为契约测试。

策略：patch `asyncio.create_subprocess_exec`，不打真 CLI；验证：
- 子进程参数拼接（flags / prompt / image path）
- 正常 envelope 解析与 RawLLMResponse 形状
- envelope.is_error / 非零 returncode / stdout 非 JSON 三类故障映射
- timeout 抛 LLMTimeoutError + 子进程被 kill+reap
- tempfile 在任何分支下都被清理
- Protocol 一致性（runtime_checkable）
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.errors import LLMCallError, LLMTimeoutError
from app.llm.base import LLMProvider, RawLLMResponse
from app.llm.claude_cli import (
    SAFETY_OFFICER_SYSTEM_PROMPT,
    ClaudeCLIProvider,
)


def _valid_envelope(result_text: str = '{"x":1}') -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result_text,
        "duration_ms": 58231,
        "duration_api_ms": 57100,
        "session_id": "sess-abc",
        "total_cost_usd": 0.0834,
        "usage": {"input_tokens": 1234, "output_tokens": 567},
    }


def _make_proc_mock(
    stdout_bytes: bytes,
    stderr_bytes: bytes = b"",
    returncode: int = 0,
) -> AsyncMock:
    """造一个看起来像 asyncio.subprocess.Process 的 mock。"""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout_bytes, stderr_bytes))
    proc.returncode = returncode
    proc.kill = lambda: None  # 同步方法
    proc.wait = AsyncMock(return_value=returncode)
    return proc


@pytest.fixture
def provider() -> ClaudeCLIProvider:
    return ClaudeCLIProvider(cli_path="claude", model="sonnet", timeout_seconds=60)


def test_provider_satisfies_runtime_protocol(provider: ClaudeCLIProvider) -> None:
    """LLMProvider 是 runtime_checkable Protocol，ClaudeCLIProvider 应当通过。"""
    assert isinstance(provider, LLMProvider)
    assert provider.name == "claude_cli"
    assert provider.model_id == "sonnet"


async def test_happy_path_returns_raw_llm_response(provider: ClaudeCLIProvider) -> None:
    envelope = _valid_envelope(result_text='{"summary":"ok"}')
    proc = _make_proc_mock(json.dumps(envelope).encode("utf-8"))

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        raw = await provider.analyze(b"\xff\xd8\xff\xe0fake-jpg", "请分析这张工地照片")

    assert isinstance(raw, RawLLMResponse)
    assert raw.content == '{"summary":"ok"}'
    assert raw.model == "sonnet"
    assert raw.latency_ms == 58231
    # provider_payload 应当完整保留 envelope（用于 cost/usage/session_id 追溯）
    assert raw.provider_payload == envelope
    assert raw.provider_payload["total_cost_usd"] == 0.0834


async def test_subprocess_args_contain_required_flags(provider: ClaudeCLIProvider) -> None:
    """关键：--allowed-tools Read / --system-prompt / --json-schema / --model 都要到位。"""
    envelope = _valid_envelope()
    proc = _make_proc_mock(json.dumps(envelope).encode("utf-8"))

    create_mock = AsyncMock(return_value=proc)
    with patch("app.llm.claude_cli.asyncio.create_subprocess_exec", new=create_mock):
        await provider.analyze(b"img", "USER_PROMPT_MARKER")

    # 取出位置参数
    call_args = create_mock.call_args
    positional = list(call_args.args)
    kwargs = call_args.kwargs

    # 第一个位置参数应当是 cli 路径
    assert positional[0] == "claude"

    # 把所有位置参数转 str 方便断言（schema 字符串很长，但成员断言即可）
    str_args = [str(a) for a in positional]

    assert "--allowed-tools" in str_args
    read_idx = str_args.index("--allowed-tools")
    assert str_args[read_idx + 1] == "Read"

    assert "--system-prompt" in str_args
    sp_idx = str_args.index("--system-prompt")
    assert str_args[sp_idx + 1] == SAFETY_OFFICER_SYSTEM_PROMPT

    assert "--model" in str_args
    m_idx = str_args.index("--model")
    assert str_args[m_idx + 1] == "sonnet"

    assert "--output-format" in str_args
    of_idx = str_args.index("--output-format")
    assert str_args[of_idx + 1] == "json"

    assert "--no-session-persistence" in str_args
    assert "--json-schema" in str_args
    js_idx = str_args.index("--json-schema")
    # schema 必须是 JSON 字符串且含 ReportPayload 的关键字段
    schema_str = str_args[js_idx + 1]
    schema = json.loads(schema_str)
    assert isinstance(schema, dict)
    # Pydantic v2 root 的 properties 含 hazards / overall_severity 等字段名
    schema_blob = json.dumps(schema, ensure_ascii=False)
    assert "hazards" in schema_blob
    assert "overall_severity" in schema_blob

    # -p 后面应当是 composed prompt：含用户 prompt + 图片路径
    assert "-p" in str_args
    p_idx = str_args.index("-p")
    composed = str_args[p_idx + 1]
    assert "USER_PROMPT_MARKER" in composed
    assert "图片路径：" in composed
    # 路径必须是绝对、可解析
    line_with_path = [ln for ln in composed.splitlines() if ln.startswith("图片路径：")][0]
    img_path_str = line_with_path.removeprefix("图片路径：").strip()
    assert Path(img_path_str).is_absolute()

    # stdout/stderr 必须接管，否则会卡在终端
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE


async def test_envelope_is_error_true_raises_llm_call_error(
    provider: ClaudeCLIProvider,
) -> None:
    envelope = {
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "Not logged in. Please run `claude login`.",
        "duration_ms": 12,
    }
    proc = _make_proc_mock(json.dumps(envelope).encode("utf-8"))

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "Not logged in" in str(exc_info.value)


async def test_nonzero_returncode_raises_llm_call_error(
    provider: ClaudeCLIProvider,
) -> None:
    proc = _make_proc_mock(
        stdout_bytes=b"",
        stderr_bytes=b"command not found: claude",
        returncode=127,
    )

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    msg = str(exc_info.value)
    assert "127" in msg
    assert "command not found" in msg


async def test_stdout_not_json_raises_llm_call_error(provider: ClaudeCLIProvider) -> None:
    proc = _make_proc_mock(b"<HTML>404 Not Found</HTML>")

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert "envelope" in str(exc_info.value)


async def test_envelope_missing_result_field_raises_llm_call_error(
    provider: ClaudeCLIProvider,
) -> None:
    """envelope 合法但缺 `result` 字段（CLI 协议漂移） → LLMCallError，不让空串混进 parser。"""
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        # 故意没有 "result"
        "duration_ms": 12,
        "session_id": "sess-x",
    }
    proc = _make_proc_mock(json.dumps(envelope).encode("utf-8"))

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with pytest.raises(LLMCallError) as exc_info:
            await provider.analyze(b"img", "prompt")

    msg = str(exc_info.value)
    assert "result" in msg
    assert "keys" in msg


async def test_timeout_kills_subprocess_and_raises_timeout_error() -> None:
    """超时分支：wait_for 抛 TimeoutError → provider 应当 kill 子进程并抛 LLMTimeoutError。"""
    provider = ClaudeCLIProvider(cli_path="claude", model="sonnet", timeout_seconds=1)

    kill_calls = {"n": 0}

    proc = AsyncMock()

    async def slow_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(10)
        return (b"", b"")

    proc.communicate = slow_communicate
    proc.returncode = None

    def fake_kill() -> None:
        kill_calls["n"] += 1

    proc.kill = fake_kill
    proc.wait = AsyncMock(return_value=-9)

    with patch(
        "app.llm.claude_cli.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with pytest.raises(LLMTimeoutError) as exc_info:
            await provider.analyze(b"img", "prompt")

    assert kill_calls["n"] == 1
    proc.wait.assert_awaited_once()
    assert "超时" in str(exc_info.value)


async def test_tempfile_cleaned_up_on_success(provider: ClaudeCLIProvider) -> None:
    """成功路径下 tempfile 应当被删除。"""
    captured_paths: list[Path] = []
    envelope = _valid_envelope()
    proc = _make_proc_mock(json.dumps(envelope).encode("utf-8"))

    create_mock = AsyncMock(return_value=proc)
    with patch("app.llm.claude_cli.asyncio.create_subprocess_exec", new=create_mock):
        await provider.analyze(b"img-bytes", "prompt")

    # 从 call_args 反推出 composed prompt 里的 image path
    str_args = [str(a) for a in create_mock.call_args.args]
    composed = str_args[str_args.index("-p") + 1]
    img_line = [ln for ln in composed.splitlines() if ln.startswith("图片路径：")][0]
    img_path = Path(img_line.removeprefix("图片路径：").strip())
    captured_paths.append(img_path)
    assert not img_path.exists(), f"临时文件未被清理：{img_path}"


async def test_tempfile_cleaned_up_on_error(provider: ClaudeCLIProvider) -> None:
    """失败路径下 tempfile 也应当被删除（finally 兜底）。"""
    proc = _make_proc_mock(
        stdout_bytes=b"",
        stderr_bytes=b"boom",
        returncode=1,
    )

    create_mock = AsyncMock(return_value=proc)
    with patch("app.llm.claude_cli.asyncio.create_subprocess_exec", new=create_mock):
        with pytest.raises(LLMCallError):
            await provider.analyze(b"img-bytes", "prompt")

    str_args = [str(a) for a in create_mock.call_args.args]
    composed = str_args[str_args.index("-p") + 1]
    img_line = [ln for ln in composed.splitlines() if ln.startswith("图片路径：")][0]
    img_path = Path(img_line.removeprefix("图片路径：").strip())
    assert not img_path.exists(), f"异常分支下临时文件未被清理：{img_path}"


async def test_tempfile_cleaned_up_on_timeout() -> None:
    """超时分支下 tempfile 也应当被删除。"""
    provider = ClaudeCLIProvider(cli_path="claude", model="sonnet", timeout_seconds=1)

    proc = AsyncMock()

    async def slow_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(10)
        return (b"", b"")

    proc.communicate = slow_communicate
    proc.returncode = None
    proc.kill = lambda: None
    proc.wait = AsyncMock(return_value=-9)

    create_mock = AsyncMock(return_value=proc)
    with patch("app.llm.claude_cli.asyncio.create_subprocess_exec", new=create_mock):
        with pytest.raises(LLMTimeoutError):
            await provider.analyze(b"img-bytes", "prompt")

    str_args = [str(a) for a in create_mock.call_args.args]
    composed = str_args[str_args.index("-p") + 1]
    img_line = [ln for ln in composed.splitlines() if ln.startswith("图片路径：")][0]
    img_path = Path(img_line.removeprefix("图片路径：").strip())
    assert not img_path.exists(), f"超时分支下临时文件未被清理：{img_path}"
