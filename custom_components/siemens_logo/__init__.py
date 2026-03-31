"""Siemens LOGO! PLC integration for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import threading

import snap7
from snap7.util import get_bool, set_bool, get_int, set_int
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_MODEL,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
    VM_MAPS,
    parse_entity_string,
    resolve_address,
)
from .coordinator import LogoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

WRITE_BLOCK_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): str,
        vol.Required("block"): str,
        vol.Required("value"): vol.Any(bool, int, float),
    }
)

READ_BLOCK_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): str,
        vol.Required("block"): str,
    }
)

_YAML_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required("block"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("address"): cv.string,
        vol.Optional("unique_id"): cv.string,
        vol.Optional("push_button", default=False): cv.boolean,
    }
)

_YAML_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_RACK, default=DEFAULT_RACK): cv.positive_int,
        vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): cv.positive_int,
        vol.Required(CONF_MODEL): vol.In(list(VM_MAPS.keys())),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL)),
        vol.Required(CONF_ENTITIES): [_YAML_ENTITY_SCHEMA],
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_YAML_DEVICE_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class LogoRuntimeData:
    """Runtime data stored on the config entry."""

    connection: LogoConnection
    coordinator: LogoDataUpdateCoordinator


type LogoConfigEntry = ConfigEntry[LogoRuntimeData]


class LogoConnection:
    """Thread-safe wrapper around the snap7 client for LOGO! PLC."""

    def __init__(self, host: str, rack: int, slot: int, port: int = 102) -> None:
        self._host = host
        self._rack = rack
        self._slot = slot
        self._port = port
        self._client = snap7.client.Client()
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            self._client.connect(self._host, self._rack, self._slot, self._port)
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
            self._client.connect(self._host, self._rack, self._slot, self._port)

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
            _LOGGER.debug(
                "write_vm_bool: byte_offset=%d bit_offset=%d value=%s data_before=%s",
                byte_offset, bit_offset, value, data.hex(),
            )
            set_bool(data, 0, bit_offset, value)
            self._client.db_write(1, byte_offset, data)
            _LOGGER.debug(
                "write_vm_bool: wrote byte_offset=%d data_after=%s",
                byte_offset, data.hex(),
            )
            readback = bytearray(self._client.db_read(1, byte_offset, 1))
            _LOGGER.debug(
                "write_vm_bool: readback byte_offset=%d data=%s (expected=%s, match=%s)",
                byte_offset, readback.hex(), data.hex(), readback == data,
            )

    def write_vm_int(self, byte_offset: int, value: int) -> None:
        """Write a 16-bit integer (2 bytes) to VM area."""
        with self._lock:
            self._ensure_connected()
            data = bytearray(2)
            set_int(data, 0, value)
            self._client.db_write(1, byte_offset, data)


def _get_runtime_data(hass: HomeAssistant, entry_id: str) -> LogoRuntimeData:
    """Look up runtime data for a config entry, raising ServiceValidationError if not found."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or not isinstance(getattr(entry, "runtime_data", None), LogoRuntimeData):
        raise ServiceValidationError(
            f"LOGO! integration entry '{entry_id}' not found or not loaded"
        )
    return entry.runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register domain-level service actions and handle YAML import."""
    for conf in config.get(DOMAIN, []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=conf,
            )
        )

    async def handle_write_block(call: ServiceCall) -> None:
        """Write a value to any LOGO! block address."""
        runtime_data = _get_runtime_data(hass, call.data["config_entry_id"])
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        model = entry.data[CONF_MODEL]

        try:
            block_name, block_number = parse_entity_string(call.data["block"])
            byte_offset, bit_offset = resolve_address(model, block_name, block_number)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        value = call.data["value"]
        try:
            if bit_offset is not None:
                await hass.async_add_executor_job(
                    runtime_data.connection.write_vm_bool,
                    byte_offset,
                    bit_offset,
                    bool(value),
                )
            else:
                await hass.async_add_executor_job(
                    runtime_data.connection.write_vm_int,
                    byte_offset,
                    int(value),
                )
        except Exception as err:
            raise HomeAssistantError(f"Failed to write to LOGO!: {err}") from err

        await runtime_data.coordinator.async_request_refresh()

    async def handle_read_block(call: ServiceCall) -> dict:
        """Read the current value of any LOGO! block address."""
        runtime_data = _get_runtime_data(hass, call.data["config_entry_id"])
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        model = entry.data[CONF_MODEL]

        try:
            block_name, block_number = parse_entity_string(call.data["block"])
            byte_offset, bit_offset = resolve_address(model, block_name, block_number)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        try:
            if bit_offset is not None:
                data = await hass.async_add_executor_job(
                    runtime_data.connection.read_vm, byte_offset, 1
                )
                return {"value": bool(get_bool(data, 0, bit_offset))}
            else:
                data = await hass.async_add_executor_job(
                    runtime_data.connection.read_vm, byte_offset, 2
                )
                return {"value": int(get_int(data, 0))}
        except Exception as err:
            raise HomeAssistantError(f"Failed to read from LOGO!: {err}") from err

    hass.services.async_register(
        DOMAIN,
        "write_block",
        handle_write_block,
        schema=WRITE_BLOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "read_block",
        handle_read_block,
        schema=READ_BLOCK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: LogoConfigEntry) -> bool:
    """Set up Siemens LOGO! from a config entry."""
    host = entry.data[CONF_HOST]
    rack = entry.data.get(CONF_RACK, DEFAULT_RACK)
    slot = entry.data.get(CONF_SLOT, DEFAULT_SLOT)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    connection = LogoConnection(host, rack, slot)

    try:
        await hass.async_add_executor_job(connection.connect)
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to LOGO! at {host}: {err}"
        ) from err

    coordinator = LogoDataUpdateCoordinator(
        hass, connection, entry.data.get(CONF_ENTITIES, []), scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LogoRuntimeData(connection=connection, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LogoConfigEntry) -> bool:
    """Unload a Siemens LOGO! config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await hass.async_add_executor_job(entry.runtime_data.connection.disconnect)

    return unload_ok
