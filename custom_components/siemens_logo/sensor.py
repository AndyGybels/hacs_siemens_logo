"""Sensor platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_int

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LogoConfigEntry
from .const import CONF_ENTITIES, CONF_HOST, CONF_MODEL
from .entity import LogoEntity, make_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: LogoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    device_info = make_device_info(entry.entry_id, entry.data[CONF_HOST], entry.data[CONF_MODEL])

    entities = [
        LogoSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            device_info=device_info,
            name=entity_cfg["name"],
            block=entity_cfg["block"],
            number=entity_cfg["number"],
            byte_offset=entity_cfg["byte_offset"],
            bit_offset=None,
            unique_id=entity_cfg.get("unique_id"),
        )
        for entity_cfg in entry.data.get(CONF_ENTITIES, [])
        if entity_cfg["platform"] == "sensor"
    ]

    async_add_entities(entities)


class LogoSensor(LogoEntity, SensorEntity):
    """A sensor reading an analog value from the LOGO! PLC."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_int(self.coordinator.data, local_offset)
