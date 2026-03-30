"""DataUpdateCoordinator for Siemens LOGO! integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, get_vm_read_ranges

_LOGGER = logging.getLogger(__name__)


class LogoDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that polls the LOGO! PLC VM area."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection,
        entities: list[dict],
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.connection = connection
        self._read_ranges = get_vm_read_ranges(entities)
        self.vm_start = self._read_ranges[0][0] if self._read_ranges else 0

    async def _async_update_data(self) -> bytearray:
        """Fetch data from the PLC."""
        try:
            vm_start = self._read_ranges[0][0]
            vm_end = max(start + size for start, size in self._read_ranges)
            full_buffer = bytearray(vm_end - vm_start)

            for start, size in self._read_ranges:
                data = await self.hass.async_add_executor_job(
                    self.connection.read_vm, start, size
                )
                offset = start - vm_start
                full_buffer[offset : offset + size] = data

            return full_buffer
        except Exception as err:
            raise UpdateFailed(f"Error communicating with LOGO! PLC: {err}") from err
