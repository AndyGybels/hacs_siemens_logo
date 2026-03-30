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
    format_address,
    get_platform,
    parse_address,
    parse_entity_string,
    resolve_address,
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


def _build_addresses_schema(entities: list[dict]) -> vol.Schema:
    """Build a schema with one address field per entity, pre-filled with current/default address."""
    return vol.Schema(
        {
            vol.Required(
                f"{e['block']}{e['number']}",
                default=format_address(e["byte_offset"], e.get("bit_offset")),
            ): str
            for e in entities
        }
    )


def _apply_address_overrides(model: str, entities: list[dict], user_input: dict) -> list[dict]:
    """Apply user-supplied address strings to entity configs. Returns updated list."""
    vm_map = VM_MAPS.get(model, {})
    updated = []
    for e in entities:
        key = f"{e['block']}{e['number']}"
        block_type = vm_map.get(e["block"], {}).get("type", "digital")
        byte_offset, bit_offset = parse_address(user_input[key], block_type)
        updated.append({**e, "byte_offset": byte_offset, "bit_offset": bit_offset})
    return updated


class SiemensLogoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens LOGO!."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict = {}
        self._entities: list[dict] = []

    async def async_step_user(self, user_input=None):
        """Step 1: Connection settings."""
        errors = {}

        if user_input is not None:
            try:
                client = snap7.client.Client()
                await self.hass.async_add_executor_job(
                    client.connect, user_input[CONF_HOST],
                    user_input.get(CONF_RACK, DEFAULT_RACK),
                    user_input.get(CONF_SLOT, DEFAULT_SLOT),
                )
                await self.hass.async_add_executor_job(client.disconnect)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._connection_data = user_input
                return await self.async_step_entities()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_entities(self, user_input=None):
        """Step 2: Enter entity names."""
        errors = {}
        model = self._connection_data[CONF_MODEL]

        if user_input is not None:
            entities = []
            for part in [p.strip() for p in user_input[CONF_ENTITIES].split(",") if p.strip()]:
                try:
                    block_name, block_number = parse_entity_string(part)
                    byte_offset, bit_offset = resolve_address(model, block_name, block_number)
                    entities.append({
                        "block": block_name,
                        "number": block_number,
                        "platform": get_platform(block_name),
                        "name": f"LOGO {block_name}{block_number}",
                        "byte_offset": byte_offset,
                        "bit_offset": bit_offset,
                    })
                except ValueError as err:
                    errors["base"] = "invalid_entity"
                    _LOGGER.error("Invalid entity '%s': %s", part, err)
                    break

            if not errors:
                self._entities = entities
                return await self.async_step_addresses()

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema({vol.Required(CONF_ENTITIES): str}),
            errors=errors,
            description_placeholders={"example": "NI1,NI2,NQ1,AI1,Q1,M1"},
        )

    async def async_step_addresses(self, user_input=None):
        """Step 3: Confirm or override the VM address for each entity."""
        errors = {}
        model = self._connection_data[CONF_MODEL]

        if user_input is not None:
            try:
                entities = _apply_address_overrides(model, self._entities, user_input)
            except (ValueError, KeyError) as err:
                errors["base"] = "invalid_address"
                _LOGGER.error("Invalid address: %s", err)
            else:
                return self.async_create_entry(
                    title=f"LOGO! {self._connection_data[CONF_HOST]}",
                    data={**self._connection_data, CONF_ENTITIES: entities},
                )

        return self.async_show_form(
            step_id="addresses",
            data_schema=_build_addresses_schema(self._entities),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SiemensLogoOptionsFlow(config_entry)


class SiemensLogoOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow to edit entities and their addresses."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self._entities: list[dict] = []

    async def async_step_init(self, user_input=None):
        """Step 1: Edit entity list."""
        errors = {}
        model = self._config_entry.data[CONF_MODEL]
        current_entities = self._config_entry.data.get(CONF_ENTITIES, [])
        current_str = ",".join(f"{e['block']}{e['number']}" for e in current_entities)

        if user_input is not None:
            entities = []
            for part in [p.strip() for p in user_input[CONF_ENTITIES].split(",") if p.strip()]:
                try:
                    block_name, block_number = parse_entity_string(part)
                    # Reuse existing address if entity was already configured
                    existing = next(
                        (e for e in current_entities
                         if e["block"] == block_name and e["number"] == block_number),
                        None,
                    )
                    if existing:
                        byte_offset = existing["byte_offset"]
                        bit_offset = existing.get("bit_offset")
                    else:
                        byte_offset, bit_offset = resolve_address(model, block_name, block_number)
                    entities.append({
                        "block": block_name,
                        "number": block_number,
                        "platform": get_platform(block_name),
                        "name": f"LOGO {block_name}{block_number}",
                        "byte_offset": byte_offset,
                        "bit_offset": bit_offset,
                    })
                except ValueError as err:
                    errors["base"] = "invalid_entity"
                    _LOGGER.error("Invalid entity '%s': %s", part, err)
                    break

            if not errors:
                self._entities = entities
                return await self.async_step_addresses()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_ENTITIES, default=current_str): str}),
            errors=errors,
        )

    async def async_step_addresses(self, user_input=None):
        """Step 2: Confirm or override VM address per entity."""
        errors = {}
        model = self._config_entry.data[CONF_MODEL]

        if user_input is not None:
            try:
                entities = _apply_address_overrides(model, self._entities, user_input)
            except (ValueError, KeyError) as err:
                errors["base"] = "invalid_address"
                _LOGGER.error("Invalid address: %s", err)
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={**self._config_entry.data, CONF_ENTITIES: entities},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="addresses",
            data_schema=_build_addresses_schema(self._entities),
            errors=errors,
        )
