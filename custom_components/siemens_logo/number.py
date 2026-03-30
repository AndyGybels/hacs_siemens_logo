"""Number platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_int

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LogoConfigEntry
from .const import CONF_ENTITIES, CONF_HOST, CONF_MODEL
from .entity import LogoEntity, make_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: LogoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! number entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    connection = entry.runtime_data.connection
    device_info = make_device_info(entry.entry_id, entry.data[CONF_HOST], entry.data[CONF_MODEL])

    entities = [
        LogoNumber(
            coordinator=coordinator,
            connection=connection,
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
        if entity_cfg["platform"] == "number"
    ]

    async_add_entities(entities)


class LogoNumber(LogoEntity, NumberEntity):
    """A number entity that writes an analog value to the LOGO! PLC."""

    _attr_native_min_value = 0
    _attr_native_max_value = 1000
    _attr_native_step = 1

    def __init__(self, connection, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connection = connection

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_int(self.coordinator.data, local_offset)

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(
            self._connection.write_vm_int, self._byte_offset, int(value),
        )
        await self.coordinator.async_request_refresh()
