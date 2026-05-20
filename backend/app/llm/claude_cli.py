"""Claude CLI Vision provider，走本地 `claude -p` 子进程 + OAuth 登录态。

设计要点（经本机实测确认）：
- `--allowed-tools Read` 必加，否则模型只看到路径字符串、看不到图。
- `--system-prompt` 全替换 Claude Code 默认 ~20K-token 的 system prompt，省 token。
- `--output-format json` 拿 envelope：`{type, subtype, is_error, result, duration_ms,
  duration_api_ms, session_id, total_cost_usd, usage, ...}`，`result` 字段是 **字符串**
  （模型的最终文本输出），不是嵌套对象。
- `--no-session-persistence` 防止泄漏 session 到磁盘。
- `--json-schema` 用 Pydantic 自动生成的 ReportPayload schema 在 CLI 层强约束输出。
- image 通过临时文件 + inline 路径传递（CLI 本身不接受 stdin 图片）。
"""

import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.errors import LLMCallError, LLMTimeoutError
from app.llm.base import RawLLMResponse
from app.schemas.report import ReportPayload

logger = logging.getLogger(__name__)


def _format_rc(rc: int) -> str:
    """Windows process exit codes can be huge unsigned numbers; render decimal + hex.

    rc=3221225794 → "3221225794 (0xC0000142)" — much easier to google.
    """
    if rc < 0:
        # POSIX signal death (rc = -SIGNUM); leave as-is.
        return str(rc)
    return f"{rc} (0x{rc:08X})"

SAFETY_OFFICER_SYSTEM_PROMPT = (
    "你是中国工地安全员，熟悉《建筑施工安全检查标准》(JGJ59-2011) 与"
    "《建筑施工高处作业安全技术规范》(JGJ80-2016) 等住建部规范。"
    "读取用户提供的工地照片，识别现场安全隐患。"
    "只输出符合用户要求的 JSON 对象，不要附加任何说明、不要用 markdown 代码块包裹。"
)

# 在 import 时一次性序列化 ReportPayload 的 JSON Schema，喂给 `--json-schema`。
# 注意：Pydantic 生成的 schema 含 $defs / Literal enums，Claude CLI 接受标准 JSON Schema。
_REPORT_JSON_SCHEMA_STR = json.dumps(ReportPayload.model_json_schema(), ensure_ascii=False)


class ClaudeCLIProvider:
    """LLMProvider 的 Claude CLI 实现。`name` 与 ReportPayload.model_meta.provider 对齐。"""

    name: str = "claude_cli"

    def __init__(self, cli_path: str, model: str, timeout_seconds: int):
        self._cli_path = cli_path
        self._model = model
        self._timeout_seconds = timeout_seconds
        self.model_id: str = model

        # 一次性诊断日志 —— provider 实例化时打印 Python 对 cli_path 的解析结果。
        # Windows 上 `claude` 通常是 .cmd shim，shutil.which 会通过 PATHEXT 找到；
        # 但 asyncio.create_subprocess_exec 走 CreateProcessW、不做 PATHEXT 解析，
        # 解析结果如果是 .cmd / .bat，subprocess_exec 直接跑会失败 (FileNotFoundError
        # 或 STATUS_DLL_INIT_FAILED rc=0xC0000142)。
        resolved = shutil.which(cli_path)
        logger.info(
            "ClaudeCLIProvider initialized",
            extra={
                "cli_path_raw": cli_path,
                "cli_path_resolved": resolved,
                "cli_path_resolved_ext": (
                    os.path.splitext(resolved)[1].lower() if resolved else None
                ),
                "model": model,
                "timeout_seconds": timeout_seconds,
                "sys_platform": sys.platform,
                "python_executable": sys.executable,
            },
        )
        if resolved is None:
            logger.error(
                "claude CLI not found on PATH at provider init —— "
                "subprocess_exec will FileNotFoundError on first call",
                extra={"cli_path_raw": cli_path},
            )
        elif sys.platform == "win32" and resolved.lower().endswith((".cmd", ".bat", ".ps1")):
            logger.warning(
                "claude CLI resolved to .cmd/.bat/.ps1 shim on Windows —— "
                "asyncio.create_subprocess_exec does NOT do PATHEXT resolution; "
                "this is the most likely cause of STATUS_DLL_INIT_FAILED / FileNotFoundError",
                extra={"cli_path_resolved": resolved},
            )

    async def analyze(self, image_bytes: bytes, prompt: str) -> RawLLMResponse:
        """跑一次 `claude -p` 子进程拿结构化报告。

        Raises:
            LLMTimeoutError: 子进程超过 timeout_seconds 未返回（已 kill+reap）。
            LLMCallError: 子进程非零退出 / envelope `is_error=True` / stdout 不是合法 JSON。
        """
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = Path(tmp.name).resolve()

            # 用户 prompt 在前（主导地位），图片路径附在末尾。Read tool 会顺路读这个路径。
            composed_prompt = f"{prompt}\n\n图片路径：{tmp_path}"

            args = (
                self._cli_path,
                "-p", composed_prompt,
                "--system-prompt", SAFETY_OFFICER_SYSTEM_PROMPT,
                "--allowed-tools", "Read",
                "--output-format", "json",
                "--no-session-persistence",
                "--model", self._model,
                "--json-schema", _REPORT_JSON_SCHEMA_STR,
            )

            logger.info(
                "spawning claude CLI",
                extra={
                    "cli_path": self._cli_path,
                    "argc": len(args),
                    "model": self._model,
                    "image_bytes": len(image_bytes),
                    "image_tmp": str(tmp_path),
                    "prompt_chars": len(composed_prompt),
                    "system_prompt_chars": len(SAFETY_OFFICER_SYSTEM_PROMPT),
                    "timeout_seconds": self._timeout_seconds,
                },
            )

            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                # Windows: CreateProcessW 找不到 .exe 时抛 WinError 2。
                # 通常是 cli_path 解析到 .cmd shim、被 create_subprocess_exec 拒掉。
                logger.error(
                    "create_subprocess_exec FileNotFoundError —— "
                    "cli_path 不是可直接 spawn 的可执行文件（多半是 .cmd shim）",
                    extra={
                        "cli_path_raw": self._cli_path,
                        "cli_path_resolved": shutil.which(self._cli_path),
                        "winerror": getattr(exc, "winerror", None),
                    },
                    exc_info=True,
                )
                raise LLMCallError(
                    f"Claude CLI 无法启动 (FileNotFoundError): {exc}"
                ) from exc

            logger.info(
                "claude CLI process spawned",
                extra={"pid": proc.pid, "cli_path": self._cli_path},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout_seconds
                )
            except TimeoutError as exc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    # 子进程在 wait_for 超时与 kill 之间自己退出了，跨平台容错。
                    pass
                await proc.wait()
                logger.error(
                    "claude CLI timed out",
                    extra={
                        "pid": proc.pid,
                        "timeout_seconds": self._timeout_seconds,
                    },
                )
                raise LLMTimeoutError(
                    f"Claude CLI 调用超时 (>{self._timeout_seconds}s)"
                ) from exc

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace")
                out_text = stdout.decode("utf-8", errors="replace")
                logger.error(
                    "claude CLI exited non-zero",
                    extra={
                        "rc": proc.returncode,
                        "rc_formatted": _format_rc(proc.returncode),
                        "stderr_len": len(stderr),
                        "stdout_len": len(stdout),
                        # 完整内容入 log（不截断）；exception message 截断给前端。
                        "stderr": err_text,
                        "stdout": out_text,
                        "cli_path_raw": self._cli_path,
                        "cli_path_resolved": shutil.which(self._cli_path),
                        "pid": proc.pid,
                    },
                )
                raise LLMCallError(
                    f"Claude CLI 非零退出 (rc={_format_rc(proc.returncode)}): "
                    f"{err_text.strip()[:500]}"
                )

            try:
                envelope: dict[str, Any] = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raw_text = stdout.decode("utf-8", errors="replace")
                raise LLMCallError(
                    f"Claude CLI stdout 不是合法 JSON envelope: {raw_text[:500]}"
                ) from exc

            if envelope.get("is_error"):
                detail = envelope.get("result", "")
                raise LLMCallError(f"Claude CLI envelope 报错: {detail}")

            # 用 `--json-schema` 时 CLI 偶尔会把结构化结果落在 envelope.structured_output
            # （dict）而 envelope.result 留空字符串（v2 实测 case_001 触发）。
            # 优先用 structured_output（dict）→ 序列化回字符串喂 parser；
            # 没有 structured_output 时回退到 result 字段。
            structured_output = envelope.get("structured_output")
            if isinstance(structured_output, dict):
                result_text = json.dumps(structured_output, ensure_ascii=False)
            elif "result" in envelope:
                result_text = envelope["result"]
                if not isinstance(result_text, str):
                    raise LLMCallError(
                        "Claude CLI envelope.result 不是字符串: "
                        f"{type(result_text).__name__}"
                    )
            else:
                raise LLMCallError(
                    "Claude CLI envelope 缺少 result 与 structured_output: "
                    f"keys={list(envelope.keys())}"
                )

            duration_ms = envelope.get("duration_ms", 0)
            if not isinstance(duration_ms, int):
                duration_ms = int(duration_ms) if duration_ms else 0

            return RawLLMResponse(
                content=result_text,
                model=self._model,
                latency_ms=duration_ms,
                provider_payload=envelope,
            )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    # tempfile 清理失败不应该掩盖业务异常；记日志的时机留给 Phase 2。
                    pass
