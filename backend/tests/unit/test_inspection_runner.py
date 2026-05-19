"""inspection_runner.run 单测 —— 重点验证 per-task 连接生命周期。

业务编排已被 test_inspection_service.py 覆盖，这里只 mock run_inspection，
聚焦"开连接 → 调服务 → 必定关连接"的 try/finally 语义。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import inspection_runner


class _NoopProvider:
    name = "fake"
    model_id = "noop"

    async def analyze(self, image_bytes: bytes, prompt: str) -> object:  # pragma: no cover
        raise AssertionError("不应被调用：run_inspection 已 mock")


async def test_runner_opens_and_closes_connection() -> None:
    fake_conn = MagicMock()
    fake_settings = MagicMock()
    fake_settings.sqlite_path = "local_data/whatever.db"

    with (
        patch("app.tasks.inspection_runner.get_settings", return_value=fake_settings),
        patch(
            "app.tasks.inspection_runner.connect", return_value=fake_conn
        ) as mock_connect,
        patch(
            "app.tasks.inspection_runner.run_inspection", new_callable=AsyncMock
        ) as mock_run,
    ):
        provider = _NoopProvider()
        await inspection_runner.run("insp-id", b"img-bytes", provider)

        mock_connect.assert_called_once_with("local_data/whatever.db")
        mock_run.assert_awaited_once_with("insp-id", b"img-bytes", provider, fake_conn)
        fake_conn.close.assert_called_once()


async def test_runner_closes_connection_even_on_exception() -> None:
    fake_conn = MagicMock()
    fake_settings = MagicMock()
    fake_settings.sqlite_path = "local_data/whatever.db"

    with (
        patch("app.tasks.inspection_runner.get_settings", return_value=fake_settings),
        patch("app.tasks.inspection_runner.connect", return_value=fake_conn),
        patch(
            "app.tasks.inspection_runner.run_inspection",
            new_callable=AsyncMock,
            side_effect=RuntimeError("service blew up"),
        ),
    ):
        provider = _NoopProvider()
        # run_inspection 抛了 → runner 不吞（按设计，runner 自己也不被消费），
        # 但 finally 必须保证 conn.close() 已调用
        with pytest.raises(RuntimeError, match="service blew up"):
            await inspection_runner.run("insp-id", b"img-bytes", provider)

        fake_conn.close.assert_called_once()
