"""Config flow for Siemens LOGO! integration."""
from __future__ import annotations

import logging

import snap7
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

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
    VM_MAPS,
    parse_entity_string,
    resolve_address,
    get_platform,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_RACK, default=DEFAULT_RACK): int,
        vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): int,
        vol.Required(CONF_MODEL, default="0BA8"): vol.In(list(VM_MAPS.keys())),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)

STEP_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES): str,
    }
)


class SiemensLogoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens LOGO!."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Connection settings."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            rack = user_input.get(CONF_RACK, DEFAULT_RACK)
            slot = user_input.get(CONF_SLOT, DEFAULT_SLOT)

            # Test connection
            try:
                client = snap7.client.Client()
                await self.hass.async_add_executor_job(
                    client.connect, host, rack, slot
                )
                await self.hass.async_add_executor_job(client.disconnect)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._connection_data = user_input
                return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_entities(self, user_input=None):
        """Step 2: Configure entities."""
        errors = {}

        if user_input is not None:
            raw = user_input[CONF_ENTITIES]
            model = self._connection_data[CONF_MODEL]
            entities = []
            parts = [p.strip() for p in raw.split(",") if p.strip()]

            for part in parts:
                try:
                    block_name, block_number = parse_entity_string(part)
                    resolve_address(model, block_name, block_number)
                    platform = get_platform(block_name)
                    entities.append(
                        {
                            "block": block_name,
                            "number": block_number,
                            "platform": platform,
                            "name": f"LOGO {block_name}{block_number}",
                        }
                    )
                except ValueError as err:
                    errors["base"] = "invalid_entity"
                    _LOGGER.error("Invalid entity '%s': %s", part, err)
                    break

            if not errors:
                data = {**self._connection_data, CONF_ENTITIES: entities}
                title = f"LOGO! {self._connection_data[CONF_HOST]}"
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="entities",
            data_schema=STEP_ENTITIES_SCHEMA,
            errors=errors,
            description_placeholders={
                "example": "NI1,NI2,NQ1,AI1,Q1,M1"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SiemensLogoOptionsFlow(config_entry)


class SiemensLogoOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow to add/remove entities."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage entity configuration."""
        errors = {}

        if user_input is not None:
            raw = user_input[CONF_ENTITIES]
            model = self._config_entry.data[CONF_MODEL]
            entities = []
            parts = [p.strip() for p in raw.split(",") if p.strip()]

            for part in parts:
                try:
                    block_name, block_number = parse_entity_string(part)
                    resolve_address(model, block_name, block_number)
                    platform = get_platform(block_name)
                    entities.append(
                        {
                            "block": block_name,
                            "number": block_number,
                            "platform": platform,
                            "name": f"LOGO {block_name}{block_number}",
                        }
                    )
                except ValueError as err:
                    errors["base"] = "invalid_entity"
                    _LOGGER.error("Invalid entity '%s': %s", part, err)
                    break

            if not errors:
                new_data = {**self._config_entry.data, CONF_ENTITIES: entities}
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        # Pre-fill with current entities
        current = self._config_entry.data.get(CONF_ENTITIES, [])
        current_str = ",".join(
            f"{e['block']}{e['number']}" for e in current
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITIES, default=current_str): str,
                }
            ),
            errors=errors,
        )
