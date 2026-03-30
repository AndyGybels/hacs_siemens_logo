"""Switch platform for Siemens LOGO! integration."""
from __future__ import annotations

import logging

from snap7.util import get_bool

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LogoConfigEntry
from .const import CONF_ENTITIES, CONF_HOST, CONF_MODEL
from .entity import LogoEntity, make_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: LogoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! switches from a config entry."""
    coordinator = entry.runtime_data.coordinator
    connection = entry.runtime_data.connection
    device_info = make_device_info(entry.entry_id, entry.data[CONF_HOST], entry.data[CONF_MODEL])

    entities = [
        LogoSwitch(
            coordinator=coordinator,
            connection=connection,
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
        if entity_cfg["platform"] == "switch"
    ]

    async_add_entities(entities)


class LogoSwitch(LogoEntity, SwitchEntity):
    """A switch that writes a digital bit to the LOGO! PLC."""

    def __init__(self, connection, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connection = connection

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_bool(self.coordinator.data, local_offset, self._bit_offset)

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.debug(
            "async_turn_on: %s byte_offset=%d bit_offset=%d",
            self._attr_name, self._byte_offset, self._bit_offset,
        )
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool, self._byte_offset, self._bit_offset, True,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.debug(
            "async_turn_off: %s byte_offset=%d bit_offset=%d",
            self._attr_name, self._byte_offset, self._bit_offset,
        )
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool, self._byte_offset, self._bit_offset, False,
        )
        await self.coordinator.async_request_refresh()
