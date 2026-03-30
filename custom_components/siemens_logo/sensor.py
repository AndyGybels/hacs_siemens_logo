"""Sensor platform for Siemens LOGO! integration."""
from __future__ import annotations

from snap7.util import get_int

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITIES, CONF_MODEL, DOMAIN, resolve_address
from .coordinator import LogoDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LOGO! sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: LogoDataUpdateCoordinator = data["coordinator"]
    model = entry.data[CONF_MODEL]

    entities = []
    for entity_cfg in entry.data.get(CONF_ENTITIES, []):
        if entity_cfg["platform"] != "sensor":
            continue
        byte_offset, _ = resolve_address(
            model, entity_cfg["block"], entity_cfg["number"]
        )
        entities.append(
            LogoSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                name=entity_cfg["name"],
                block=entity_cfg["block"],
                number=entity_cfg["number"],
                byte_offset=byte_offset,
            )
        )

    async_add_entities(entities)


class LogoSensor(CoordinatorEntity, SensorEntity):
    """A sensor reading an analog value from the LOGO! PLC."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: LogoDataUpdateCoordinator,
        entry_id: str,
        name: str,
        block: str,
        number: int,
        byte_offset: int,
    ) -> None:
        super().__init__(coordinator)
        self._byte_offset = byte_offset
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{block}{number}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        local_offset = self._byte_offset - self.coordinator.vm_start
        return get_int(self.coordinator.data, local_offset)
