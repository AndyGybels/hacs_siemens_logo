"""Tests for siemens_logo switch platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from siemens_logo.switch import LogoSwitch


def _make_device_info():
    from homeassistant.helpers.device_registry import DeviceInfo
    return DeviceInfo(identifiers={("siemens_logo", "test_entry")})


def _make_coordinator(vm_data: bytearray, vm_start: int = 0):
    coord = MagicMock()
    coord.data = vm_data
    coord.vm_start = vm_start
    coord.async_request_refresh = AsyncMock()
    return coord


def _make_switch(byte_offset: int = 0, bit_offset: int = 0, vm_data: bytearray | None = None):
    if vm_data is None:
        vm_data = bytearray(max(byte_offset + 1, 2))
    coordinator = _make_coordinator(vm_data, vm_start=0)
    connection = MagicMock()
    connection.write_vm_bool = MagicMock()
    switch = LogoSwitch(
        connection=connection,
        coordinator=coordinator,
        entry_id="test_entry",
        device_info=_make_device_info(),
        name="Test Switch",
        block="NI",
        number=1,
        byte_offset=byte_offset,
        bit_offset=bit_offset,
        unique_id=None,
    )
    switch.hass = MagicMock()
    switch.hass.async_add_executor_job = AsyncMock()
    return switch


class TestLogoSwitchIsOn:
    def test_returns_none_when_no_data(self) -> None:
        coordinator = _make_coordinator(None)
        switch = LogoSwitch(
            connection=MagicMock(),
            coordinator=coordinator,
            entry_id="e",
            device_info=_make_device_info(),
            name="S",
            block="NI",
            number=1,
            byte_offset=0,
            bit_offset=0,
            unique_id=None,
        )
        assert switch.is_on is None

    def test_returns_false_when_bit_is_zero(self) -> None:
        vm_data = bytearray(b"\x00")
        switch = _make_switch(byte_offset=0, bit_offset=0, vm_data=vm_data)
        assert switch.is_on is False

    def test_returns_true_when_bit_is_set(self) -> None:
        # bit 0 of byte 0 = 0x01
        vm_data = bytearray(b"\x01")
        switch = _make_switch(byte_offset=0, bit_offset=0, vm_data=vm_data)
        assert switch.is_on is True

    def test_reads_correct_bit_from_byte(self) -> None:
        # bit 1 (second bit) = 0x02
        vm_data = bytearray(b"\x02")
        switch = _make_switch(byte_offset=0, bit_offset=1, vm_data=vm_data)
        assert switch.is_on is True

    def test_uses_local_offset_relative_to_vm_start(self) -> None:
        # Entity at byte_offset=5, vm_start=4 → local_offset=1
        vm_data = bytearray(b"\x00\x01")  # byte 1 has bit 0 set
        coordinator = _make_coordinator(vm_data, vm_start=4)
        switch = LogoSwitch(
            connection=MagicMock(),
            coordinator=coordinator,
            entry_id="e",
            device_info=_make_device_info(),
            name="S",
            block="NI",
            number=1,
            byte_offset=5,
            bit_offset=0,
            unique_id=None,
        )
        assert switch.is_on is True


class TestLogoSwitchTurnOnOff:
    async def test_turn_on_calls_write_vm_bool_true(self) -> None:
        switch = _make_switch(byte_offset=0, bit_offset=0)
        await switch.async_turn_on()
        switch.hass.async_add_executor_job.assert_called_once_with(
            switch._connection.write_vm_bool, 0, 0, True
        )
        switch.coordinator.async_request_refresh.assert_called_once()

    async def test_turn_off_calls_write_vm_bool_false(self) -> None:
        switch = _make_switch(byte_offset=0, bit_offset=2)
        await switch.async_turn_off()
        switch.hass.async_add_executor_job.assert_called_once_with(
            switch._connection.write_vm_bool, 0, 2, False
        )
        switch.coordinator.async_request_refresh.assert_called_once()


class TestLogoSwitchUniqueId:
    def test_auto_generates_unique_id_when_none(self) -> None:
        switch = _make_switch()
        assert switch._attr_unique_id == "test_entry_NI1"

    def test_uses_provided_unique_id(self) -> None:
        coordinator = _make_coordinator(bytearray(1))
        switch = LogoSwitch(
            connection=MagicMock(),
            coordinator=coordinator,
            entry_id="e",
            device_info=_make_device_info(),
            name="S",
            block="NI",
            number=1,
            byte_offset=0,
            bit_offset=0,
            unique_id="my_custom_uid",
        )
        assert switch._attr_unique_id == "my_custom_uid"

    def test_has_entity_name_is_true(self) -> None:
        switch = _make_switch()
        assert switch._attr_has_entity_name is True

    def test_device_info_is_set(self) -> None:
        switch = _make_switch()
        assert switch._attr_device_info is not None
