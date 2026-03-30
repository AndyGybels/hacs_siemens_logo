"""Tests for siemens_logo __init__ (setup/unload)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from siemens_logo import LogoConnection, async_setup_entry, async_unload_entry
from siemens_logo.const import DOMAIN

from .conftest import MOCK_ENTRY_DATA


def _make_entry(data=None):
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = data or MOCK_ENTRY_DATA.copy()
    return entry


def _make_hass(entry_id="test_entry_id"):
    hass = MagicMock()
    hass.data = {}
    hass.async_add_executor_job = AsyncMock(return_value=None)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


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
        # Should read once (to modify bit), write once, then readback once
        assert mock_snap7_client.db_read.call_count >= 1
        assert mock_snap7_client.db_write.call_count == 1

    def test_write_vm_int_writes_two_bytes(self, mock_snap7_client) -> None:
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        conn.write_vm_int(1032, 42)
        mock_snap7_client.db_write.assert_called_once()
        _, args, _ = mock_snap7_client.db_write.mock_calls[0]
        # db_write(1, byte_offset, data) - data should be 2 bytes
        assert args[0] == 1
        assert args[1] == 1032
        assert len(args[2]) == 2

    def test_reconnects_when_disconnected(self, mock_snap7_client) -> None:
        mock_snap7_client.get_connected.return_value = False
        mock_snap7_client.db_read.return_value = bytearray(1)
        conn = LogoConnection("192.168.1.1", 0, 1)
        conn._client = mock_snap7_client
        conn.read_vm(0, 1)
        mock_snap7_client.connect.assert_called_once_with("192.168.1.1", 0, 1)


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    async def test_setup_registers_domain_data(self) -> None:
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
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        assert "connection" in hass.data[DOMAIN][entry.entry_id]
        assert "coordinator" in hass.data[DOMAIN][entry.entry_id]

    async def test_setup_returns_false_on_connect_error(self) -> None:
        hass = _make_hass()
        entry = _make_entry()
        hass.async_add_executor_job = AsyncMock(side_effect=Exception("connection refused"))

        with patch("siemens_logo.LogoConnection"):
            result = await async_setup_entry(hass, entry)

        assert result is False

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

    async def test_unload_disconnects_and_removes_data(self) -> None:
        hass = _make_hass()
        entry = _make_entry()

        mock_conn = MagicMock()
        hass.data = {
            DOMAIN: {
                entry.entry_id: {
                    "connection": mock_conn,
                    "coordinator": MagicMock(),
                }
            }
        }

        result = await async_unload_entry(hass, entry)

        assert result is True
        assert entry.entry_id not in hass.data[DOMAIN]
        # disconnect should have been scheduled via executor
        hass.async_add_executor_job.assert_called()

    async def test_unload_preserves_data_on_platform_failure(self) -> None:
        hass = _make_hass()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        entry = _make_entry()

        mock_conn = MagicMock()
        hass.data = {
            DOMAIN: {
                entry.entry_id: {
                    "connection": mock_conn,
                    "coordinator": MagicMock(),
                }
            }
        }

        result = await async_unload_entry(hass, entry)

        assert result is False
        # Data should still be there since unload failed
        assert entry.entry_id in hass.data[DOMAIN]
