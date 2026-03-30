"""Number platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_int

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITIES, CONF_MODEL, DOMAIN, resolve_address
from .coordinator import LogoDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: LogoDataUpdateCoordinator = data["coordinator"]
    connection = data["connection"]
    model = entry.data[CONF_MODEL]

    entities = []
    for entity_cfg in entry.data.get(CONF_ENTITIES, []):
        if entity_cfg["platform"] != "number":
            continue
        byte_offset, _ = resolve_address(
            model, entity_cfg["block"], entity_cfg["number"]
        )
        entities.append(
            LogoNumber(
                coordinator=coordinator,
                connection=connection,
                entry_id=entry.entry_id,
                name=entity_cfg["name"],
                block=entity_cfg["block"],
                number=entity_cfg["number"],
                byte_offset=byte_offset,
            )
        )

    async_add_entities(entities)


class LogoNumber(CoordinatorEntity, NumberEntity):
    """A number entity that writes an analog value to the LOGO! PLC."""

    _attr_native_min_value = 0
    _attr_native_max_value = 1000
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: LogoDataUpdateCoordinator,
        connection,
        entry_id: str,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
    ) -> None:
        super().__init__(coordinator)
        self._connection = connection
        self._byte_offset = byte_offset
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{block}{number}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_int(self.coordinator.data, local_offset)

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(
            self._connection.write_vm_int,
            self._byte_offset,
            int(value),
        )
        await self.coordinator.async_request_refresh()
