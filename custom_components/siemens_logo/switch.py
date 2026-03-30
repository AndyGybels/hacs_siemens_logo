"""Switch platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_bool

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITIES, CONF_MODEL, DOMAIN, resolve_address
from .coordinator import LogoDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: LogoDataUpdateCoordinator = data["coordinator"]
    connection = data["connection"]
    model = entry.data[CONF_MODEL]

    entities = []
    for entity_cfg in entry.data.get(CONF_ENTITIES, []):
        if entity_cfg["platform"] != "switch":
            continue
        byte_offset, bit_offset = resolve_address(
            model, entity_cfg["block"], entity_cfg["number"]
        )
        entities.append(
            LogoSwitch(
                coordinator=coordinator,
                connection=connection,
                entry_id=entry.entry_id,
                name=entity_cfg["name"],
                block=entity_cfg["block"],
                number=entity_cfg["number"],
                byte_offset=byte_offset,
                bit_offset=bit_offset,
            )
        )

    async_add_entities(entities)


class LogoSwitch(CoordinatorEntity, SwitchEntity):
    """A switch that writes a digital bit to the LOGO! PLC."""

    def __init__(
        self,
        coordinator: LogoDataUpdateCoordinator,
        connection,
        entry_id: str,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
        bit_offset: int,
    ) -> None:
        super().__init__(coordinator)
        self._connection = connection
        self._byte_offset = byte_offset
        self._bit_offset = bit_offset
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{block}{number}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_bool(self.coordinator.data, local_offset, self._bit_offset)

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool,
            self._byte_offset,
            self._bit_offset,
            True,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(
            self._connection.write_vm_bool,
            self._byte_offset,
            self._bit_offset,
            False,
        )
        await self.coordinator.async_request_refresh()
