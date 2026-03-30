"""Button platform for Siemens LOGO! integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BUTTON_PULSE_MS, CONF_ENTITIES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! push buttons from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    connection = data["connection"]

    entities = [
        LogoButton(
            connection=connection,
            entry_id=entry.entry_id,
            name=entity_cfg["name"],
            block=entity_cfg["block"],
            number=entity_cfg["number"],
            byte_offset=entity_cfg["byte_offset"],
            bit_offset=entity_cfg["bit_offset"],
            unique_id=entity_cfg.get("unique_id"),
        )
        for entity_cfg in entry.data.get(CONF_ENTITIES, [])
        if entity_cfg["platform"] == "button"
    ]

    async_add_entities(entities)


class LogoButton(ButtonEntity):
    """A momentary push button that pulses a digital bit on the LOGO! PLC."""

    def __init__(
        self,
        connection,
        entry_id: str,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
        bit_offset: int,
        unique_id: str | None,
    ) -> None:
        self._connection = connection
        self._byte_offset = byte_offset
        self._bit_offset = bit_offset
        self._attr_name = name
        self._attr_unique_id = unique_id or f"{entry_id}_{block}{number}"

    async def async_press(self) -> None:
        _LOGGER.debug(
            "async_press: %s byte_offset=%d bit_offset=%d pulse=%dms",
            self._attr_name, self._byte_offset, self._bit_offset, BUTTON_PULSE_MS,
        )
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool, self._byte_offset, self._bit_offset, True
        )
        await asyncio.sleep(BUTTON_PULSE_MS / 1000)
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool, self._byte_offset, self._bit_offset, False
        )
