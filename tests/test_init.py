"""Tests for siemens_logo __init__ (setup/unload)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import ConfigEntryNotReady

from siemens_logo import (
    DOMAIN,
    LogoConnection,
    LogoRuntimeData,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)

from .conftest import MOCK_ENTRY_DATA


def _make_entry(data=None):
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = data or MOCK_ENTRY_DATA.copy()
    entry.runtime_data = None
    return entry


def _make_hass():
    hass = MagicMock()
    hass.data = {}
    hass.async_add_executor_job = AsyncMock(return_value=None)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


def _make_yaml_config(**overrides) -> dict:
    base = {
        "host": "192.168.1.50",
        "rack": 0,
        "slot": 1,
        "model": "0BA8",
        "scan_interval": 1000,
        "entities": [{"block": "NI1", "name": "Pump"}],
    }
    base.update(overrides)
    return base


class TestAsyncSetup:
    """Tests for async_setup — YAML import dispatch and service registration."""

    async def test_returns_true_with_no_yaml_config(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()
        result = await async_setup(hass, {})
        assert result is True

    async def test_fires_import_flow_for_each_yaml_device(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()
        hass.async_create_task = MagicMock()
        hass.config_entries.flow.async_init = AsyncMock(return_value=None)

        config = {
            DOMAIN: [
                _make_yaml_config(host="192.168.1.10"),
                _make_yaml_config(host="192.168.1.11"),
            ]
        }
        await async_setup(hass, config)

        assert hass.async_create_task.call_count == 2

    async def test_import_flow_called_with_source_import(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()

        captured_coros = []
        hass.async_create_task = lambda coro: captured_coros.append(coro)
        hass.config_entries.flow.async_init = AsyncMock(return_value=None)

        config = {DOMAIN: [_make_yaml_config()]}
        await async_setup(hass, config)

        # Drain the coroutine so async_init is actually called
        assert len(captured_coros) == 1
        await captured_coros[0]

        hass.config_entries.flow.async_init.assert_called_once()
        _, kwargs = hass.config_entries.flow.async_init.call_args
        assert kwargs["context"]["source"] == "import"

    async def test_no_import_flow_when_domain_absent(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()
        hass.async_create_task = MagicMock()

        await async_setup(hass, {"other_domain": {}})

        hass.async_create_task.assert_not_called()

    async def test_registers_write_block_service(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()

        await async_setup(hass, {})

        registered = [
            call.args[1]
            for call in hass.services.async_register.call_args_list
        ]
        assert "write_block" in registered

    async def test_registers_read_block_service(self) -> None:
        hass = _make_hass()
        hass.services = MagicMock()
        hass.services.async_register = MagicMock()

        await async_setup(hass, {})

        registered = [
            call.args[1]
            for call in hass.services.async_register.call_args_list
        ]
        assert "read_block" in registered


class TestLogoConnection:
    """Unit tests for LogoConnection."""

    def test_read_vm_returns_bytearray(self, mock_snap7_client) -> None:
        mock_snap7_client.db_read.return_value = bytearray(b"\x01\x02")
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        result = conn.read_vm(0, 2)
        assert isinstance(result, bytearray)
        assert result == bytearray(b"\x01\x02")
        mock_snap7_client.db_read.assert_called_once_with(1, 0, 2)

    def test_write_vm_bool_reads_then_writes(self, mock_snap7_client) -> None:
        mock_snap7_client.db_read.return_value = bytearray(1)
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        conn.write_vm_bool(0, 0, True)
        assert mock_snap7_client.db_read.call_count >= 1
        assert mock_snap7_client.db_write.call_count == 1

    def test_write_vm_int_writes_two_bytes(self, mock_snap7_client) -> None:
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        conn.write_vm_int(1032, 42)
        mock_snap7_client.db_write.assert_called_once()
        _, args, _ = mock_snap7_client.db_write.mock_calls[0]
        assert args[0] == 1
        assert args[1] == 1032
        assert len(args[2]) == 2

    def test_reconnects_when_disconnected(self, mock_snap7_client) -> None:
        mock_snap7_client.get_connected.return_value = False
        mock_snap7_client.db_read.return_value = bytearray(1)
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        conn.read_vm(0, 1)
        mock_snap7_client.connect.assert_called_once_with("192.168.1.1", 0, 1, 102)


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    async def test_setup_stores_runtime_data(self) -> None:
        hass = _make_hass()
        entry = _make_entry()

        with (
            patch("siemens_logo.LogoConnection") as MockConn,
            patch("siemens_logo.LogoDataUpdateCoordinator") as MockCoord,
        ):
            mock_conn = MagicMock()
            MockConn.return_value = mock_conn
            mock_coord = MagicMock()
            mock_coord.async_config_entry_first_refresh = AsyncMock()
            MockCoord.return_value = mock_coord

            result = await async_setup_entry(hass, entry)

        assert result is True
        assert isinstance(entry.runtime_data, LogoRuntimeData)
        assert entry.runtime_data.connection is mock_conn
        assert entry.runtime_data.coordinator is mock_coord

    async def test_setup_raises_config_entry_not_ready_on_connect_error(self) -> None:
        hass = _make_hass()
        entry = _make_entry()
        hass.async_add_executor_job = AsyncMock(side_effect=Exception("connection refused"))

        with patch("siemens_logo.LogoConnection"):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    async def test_setup_forwards_to_all_platforms(self) -> None:
        hass = _make_hass()
        entry = _make_entry()

        with (
            patch("siemens_logo.LogoConnection"),
            patch("siemens_logo.LogoDataUpdateCoordinator") as MockCoord,
        ):
            mock_coord = MagicMock()
            mock_coord.async_config_entry_first_refresh = AsyncMock()
            MockCoord.return_value = mock_coord

            await async_setup_entry(hass, entry)

        hass.config_entries.async_forward_entry_setups.assert_called_once()


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry."""

    async def test_unload_disconnects_connection(self) -> None:
        hass = _make_hass()
        entry = _make_entry()
        mock_conn = MagicMock()
        entry.runtime_data = LogoRuntimeData(
            connection=mock_conn,
            coordinator=MagicMock(),
        )

        result = await async_unload_entry(hass, entry)

        assert result is True
        hass.async_add_executor_job.assert_called_with(mock_conn.disconnect)

    async def test_unload_does_not_disconnect_on_platform_failure(self) -> None:
        hass = _make_hass()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        entry = _make_entry()
        mock_conn = MagicMock()
        entry.runtime_data = LogoRuntimeData(
            connection=mock_conn,
            coordinator=MagicMock(),
        )

        result = await async_unload_entry(hass, entry)

        assert result is False
        hass.async_add_executor_job.assert_not_called()
