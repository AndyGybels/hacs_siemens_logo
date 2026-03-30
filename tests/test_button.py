"""Tests for siemens_logo button platform."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from siemens_logo.button import LogoButton
from siemens_logo.const import BUTTON_PULSE_MS


def _make_button(byte_offset: int = 0, bit_offset: int = 0, unique_id: str | None = None):
    connection = MagicMock()
    button = LogoButton(
        connection=connection,
        entry_id="test_entry",
        name="Test Button",
        block="NI",
        number=1,
        byte_offset=byte_offset,
        bit_offset=bit_offset,
        unique_id=unique_id,
    )
    button.hass = MagicMock()
    button.hass.async_add_executor_job = AsyncMock()
    return button


class TestLogoButton:
    async def test_press_sets_bit_then_clears(self) -> None:
        button = _make_button(byte_offset=0, bit_offset=0)

        with patch("siemens_logo.button.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await button.async_press()

        calls = button.hass.async_add_executor_job.call_args_list
        assert len(calls) == 2
        # First call: write True
        assert calls[0] == call(button._connection.write_vm_bool, 0, 0, True)
        # Second call: write False
        assert calls[1] == call(button._connection.write_vm_bool, 0, 0, False)

    async def test_press_sleeps_for_pulse_duration(self) -> None:
        button = _make_button()

        with patch("siemens_logo.button.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await button.async_press()

        mock_sleep.assert_called_once_with(BUTTON_PULSE_MS / 1000)

    async def test_press_uses_correct_bit_offset(self) -> None:
        button = _make_button(byte_offset=1, bit_offset=3)

        with patch("siemens_logo.button.asyncio.sleep", new_callable=AsyncMock):
            await button.async_press()

        calls = button.hass.async_add_executor_job.call_args_list
        assert calls[0] == call(button._connection.write_vm_bool, 1, 3, True)
        assert calls[1] == call(button._connection.write_vm_bool, 1, 3, False)

    def test_auto_generates_unique_id(self) -> None:
        button = _make_button()
        assert button._attr_unique_id == "test_entry_NI1"

    def test_uses_provided_unique_id(self) -> None:
        button = _make_button(unique_id="custom_uid")
        assert button._attr_unique_id == "custom_uid"

    def test_name_is_set(self) -> None:
        button = _make_button()
        assert button._attr_name == "Test Button"
