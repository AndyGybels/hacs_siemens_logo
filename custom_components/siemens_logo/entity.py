"""Base entity class for Siemens LOGO! integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LogoDataUpdateCoordinator


def make_device_info(entry_id: str, host: str, model: str) -> DeviceInfo:
    """Build a DeviceInfo for a LOGO! PLC config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=f"LOGO! {host}",
        manufacturer="Siemens",
        model=model,
    )


class LogoEntity(CoordinatorEntity[LogoDataUpdateCoordinator]):
    """Base class for LOGO! entities backed by the coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoDataUpdateCoordinator,
        entry_id: str,
        device_info: DeviceInfo,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
        bit_offset: int | None,
        unique_id: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._byte_offset = byte_offset
        self._bit_offset = bit_offset
        self._attr_name = name
        self._attr_unique_id = unique_id or f"{entry_id}_{block}{number}"
        self._attr_device_info = device_info
