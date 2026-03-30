"""Binary sensor platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_bool

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LogoConfigEntry
from .const import CONF_ENTITIES, CONF_HOST, CONF_MODEL
from .entity import LogoEntity, make_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: LogoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    device_info = make_device_info(entry.entry_id, entry.data[CONF_HOST], entry.data[CONF_MODEL])

    entities = [
        LogoBinarySensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            device_info=device_info,
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


class LogoBinarySensor(LogoEntity, BinarySensorEntity):
    """A binary sensor reading a digital bit from the LOGO! PLC."""

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_bool(self.coordinator.data, local_offset, self._bit_offset)
