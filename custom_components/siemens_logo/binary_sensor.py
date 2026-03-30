"""Binary sensor platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_bool

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITIES, DOMAIN
from .coordinator import LogoDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: LogoDataUpdateCoordinator = data["coordinator"]

    entities = [
        LogoBinarySensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            name=entity_cfg["name"],
            block=entity_cfg["block"],
            number=entity_cfg["number"],
            byte_offset=entity_cfg["byte_offset"],
            bit_offset=entity_cfg["bit_offset"],
            unique_id=entity_cfg.get("unique_id"),
        )
        for entity_cfg in entry.data.get(CONF_ENTITIES, [])
        if entity_cfg["platform"] == "binary_sensor"
    ]

    async_add_entities(entities)


class LogoBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A binary sensor reading a digital bit from the LOGO! PLC."""

    def __init__(
        self,
        coordinator: LogoDataUpdateCoordinator,
        entry_id: str,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
        bit_offset: int,
        unique_id: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._byte_offset = byte_offset
        self._bit_offset = bit_offset
        self._attr_name = name
        self._attr_unique_id = unique_id or f"{entry_id}_{block}{number}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_bool(self.coordinator.data, local_offset, self._bit_offset)
