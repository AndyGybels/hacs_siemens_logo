"""Siemens LOGO! PLC integration for Home Assistant."""
from __future__ import annotations

import logging
import threading

import snap7
from snap7.util import get_bool, set_bool, get_int, set_int

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import LogoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class LogoConnection:
    """Thread-safe wrapper around the snap7 client for LOGO! PLC."""

    def __init__(self, host: str, rack: int, slot: int) -> None:
        self._host = host
        self._rack = rack
        self._slot = slot
        self._client = snap7.client.Client()
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            self._client.connect(self._host, self._rack, self._slot)
            _LOGGER.info("Connected to LOGO! at %s", self._host)

    def disconnect(self) -> None:
        with self._lock:
            self._client.disconnect()
            _LOGGER.info("Disconnected from LOGO! at %s", self._host)

    @property
    def is_connected(self) -> bool:
        return self._client.get_connected()

    def _ensure_connected(self) -> None:
        """Reconnect if the connection was lost."""
        if not self._client.get_connected():
            _LOGGER.warning("LOGO! connection lost, reconnecting...")
            self._client.connect(self._host, self._rack, self._slot)

    def read_vm(self, start: int, size: int) -> bytearray:
        """Read bytes from VM area (DB1)."""
        with self._lock:
            self._ensure_connected()
            return bytearray(self._client.db_read(1, start, size))

    def write_vm_bool(self, byte_offset: int, bit_offset: int, value: bool) -> None:
        """Write a single bit in VM area (read-modify-write)."""
        with self._lock:
            self._ensure_connected()
            data = bytearray(self._client.db_read(1, byte_offset, 1))
            set_bool(data, 0, bit_offset, value)
            self._client.db_write(1, byte_offset, data)

    def write_vm_int(self, byte_offset: int, value: int) -> None:
        """Write a 16-bit integer (2 bytes) to VM area."""
        with self._lock:
            self._ensure_connected()
            data = bytearray(2)
            set_int(data, 0, value)
            self._client.db_write(1, byte_offset, data)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Siemens LOGO! from a config entry."""
    host = entry.data[CONF_HOST]
    rack = entry.data.get(CONF_RACK, DEFAULT_RACK)
    slot = entry.data.get(CONF_SLOT, DEFAULT_SLOT)
    model = entry.data[CONF_MODEL]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    connection = LogoConnection(host, rack, slot)

    try:
        await hass.async_add_executor_job(connection.connect)
    except Exception as err:
        _LOGGER.error("Failed to connect to LOGO! at %s: %s", host, err)
        return False

    coordinator = LogoDataUpdateCoordinator(
        hass, connection, model, scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "connection": connection,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Siemens LOGO! config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(data["connection"].disconnect)

    return unload_ok
