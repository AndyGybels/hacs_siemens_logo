"""Config flow for Siemens LOGO! integration."""

from __future__ import annotations

import logging

import snap7
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import section

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
    VM_MAPS,
    WRITABLE_DIGITAL,
    format_address,
    get_platform,
    parse_address,
    parse_entity_string,
    resolve_address,
)

_LOGGER = logging.getLogger(__name__)


def _connection_schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_RACK, default=defaults.get(CONF_RACK, DEFAULT_RACK)): int,
            vol.Optional(CONF_SLOT, default=defaults.get(CONF_SLOT, DEFAULT_SLOT)): int,
            vol.Required(CONF_MODEL, default=defaults.get(CONF_MODEL, "0BA8")): vol.In(
                list(VM_MAPS.keys())
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL)),
        }
    )


def _build_addresses_schema(entities: list[dict]) -> vol.Schema:
    """Build one collapsible section per entity so each block is visually separated."""
    outer: dict = {}
    for e in entities:
        key = f"{e['block']}{e['number']}"
        inner: dict = {
            vol.Required(
                key, default=format_address(e["byte_offset"], e.get("bit_offset"))
            ): str,
            vol.Required(
                f"{key}_name", default=e.get("name", f"LOGO {key}")
            ): str,
            vol.Optional(
                f"{key}_unique_id", default=e.get("unique_id", "")
            ): str,
        }
        if e["block"] in WRITABLE_DIGITAL:
            inner[
                vol.Optional(f"{key}_push", default=e.get("platform") == "button")
            ] = bool
        outer[vol.Required(key)] = section(vol.Schema(inner), {"collapsed": False})
    return vol.Schema(outer)


def _flatten_section_input(user_input: dict) -> dict:
    """Flatten section-nested user_input into a single-level dict for _apply_address_overrides."""
    flat: dict = {}
    for key, value in user_input.items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _apply_address_overrides(
    model: str, entities: list[dict], user_input: dict
) -> list[dict]:
    """Apply user-supplied address strings, names, unique IDs and push button flags to entity configs."""
    vm_map = VM_MAPS.get(model, {})
    updated = []
    for e in entities:
        key = f"{e['block']}{e['number']}"
        block_type = vm_map.get(e["block"], {}).get("type", "digital")
        byte_offset, bit_offset = parse_address(user_input[key], block_type)
        is_push = user_input.get(f"{key}_push", False)
        platform = "button" if is_push else get_platform(e["block"])
        name = user_input.get(f"{key}_name") or f"LOGO {key}"
        unique_id = user_input.get(f"{key}_unique_id") or None
        updated.append(
            {
                **e,
                "byte_offset": byte_offset,
                "bit_offset": bit_offset,
                "platform": platform,
                "name": name,
                "unique_id": unique_id,
            }
        )
    return updated


async def _test_connection(hass, host: str, rack: int, slot: int) -> bool:
    """Return True if connection succeeds."""
    try:
        client = snap7.client.Client()
        await hass.async_add_executor_job(client.connect, host, rack, slot)
        await hass.async_add_executor_job(client.disconnect)
        return True
    except Exception:
        return False


def _parse_entities(
    model: str, raw: str, current_entities: list[dict]
) -> tuple[list[dict], str | None]:
    """Parse entity string. Returns (entities, error_key) where error_key is None on success."""
    entities = []
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        try:
            block_name, block_number = parse_entity_string(part)
            existing = next(
                (
                    e
                    for e in current_entities
                    if e["block"] == block_name and e["number"] == block_number
                ),
                None,
            )
            if existing:
                byte_offset = existing["byte_offset"]
                bit_offset = existing.get("bit_offset")
                platform = existing.get("platform", get_platform(block_name))
                name = existing.get("name", f"LOGO {block_name}{block_number}")
                unique_id = existing.get("unique_id")
            else:
                byte_offset, bit_offset = resolve_address(
                    model, block_name, block_number
                )
                platform = get_platform(block_name)
                name = f"LOGO {block_name}{block_number}"
                unique_id = None
            entities.append(
                {
                    "block": block_name,
                    "number": block_number,
                    "platform": platform,
                    "name": name,
                    "unique_id": unique_id,
                    "byte_offset": byte_offset,
                    "bit_offset": bit_offset,
                }
            )
        except ValueError as err:
            _LOGGER.error("Invalid entity '%s': %s", part, err)
            return [], "invalid_entity"
    return entities, None


class SiemensLogoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens LOGO!."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict = {}
        self._entities: list[dict] = []

    # ------------------------------------------------------------------
    # YAML import
    # ------------------------------------------------------------------

    async def async_step_import(self, import_data: dict):
        """Create or update a config entry from a configuration.yaml entry."""
        await self.async_set_unique_id(import_data[CONF_HOST])

        model = import_data[CONF_MODEL]
        vm_map = VM_MAPS.get(model, {})
        entities = []
        for e in import_data[CONF_ENTITIES]:
            try:
                block_name, block_number = parse_entity_string(e["block"])
                if "address" in e:
                    block_type = vm_map.get(block_name, {}).get("type", "digital")
                    byte_offset, bit_offset = parse_address(e["address"], block_type)
                else:
                    byte_offset, bit_offset = resolve_address(model, block_name, block_number)
            except ValueError as err:
                _LOGGER.error("Invalid YAML entity '%s': %s", e["block"], err)
                return self.async_abort(reason="invalid_entity")

            is_push = e.get("push_button", False)
            platform = "button" if is_push else get_platform(block_name)
            name = e.get("name") or f"LOGO {block_name}{block_number}"
            unique_id = e.get("unique_id") or None
            entities.append(
                {
                    "block": block_name,
                    "number": block_number,
                    "platform": platform,
                    "name": name,
                    "unique_id": unique_id,
                    "byte_offset": byte_offset,
                    "bit_offset": bit_offset,
                }
            )

        new_data = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_RACK: import_data.get(CONF_RACK, DEFAULT_RACK),
            CONF_SLOT: import_data.get(CONF_SLOT, DEFAULT_SLOT),
            CONF_MODEL: model,
            CONF_SCAN_INTERVAL: import_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_ENTITIES: entities,
        }

        self._abort_if_unique_id_configured(updates=new_data)

        return self.async_create_entry(
            title=f"LOGO! {import_data[CONF_HOST]}",
            data=new_data,
        )

    # ------------------------------------------------------------------
    # Initial setup
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        """Step 1: Connection settings."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            if not await _test_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_RACK, DEFAULT_RACK),
                user_input.get(CONF_SLOT, DEFAULT_SLOT),
            ):
                errors["base"] = "cannot_connect"
            else:
                self._connection_data = user_input
                return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_entities(self, user_input=None):
        """Step 2: Enter entity names."""
        errors = {}
        if user_input is not None:
            entities, error = _parse_entities(
                self._connection_data[CONF_MODEL], user_input[CONF_ENTITIES], []
            )
            if error:
                errors["base"] = error
            else:
                self._entities = entities
                return await self.async_step_addresses()

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema({vol.Required(CONF_ENTITIES): str}),
            errors=errors,
            description_placeholders={"example": "NI1,NI2,NQ1,AI1,Q1,M1"},
        )

    async def async_step_addresses(self, user_input=None):
        """Step 3: Confirm or override VM address per entity."""
        errors = {}
        if user_input is not None:
            try:
                entities = _apply_address_overrides(
                    self._connection_data[CONF_MODEL],
                    self._entities,
                    _flatten_section_input(user_input),
                )
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

    # ------------------------------------------------------------------
    # Reconfigure (change connection settings on existing entry)
    # ------------------------------------------------------------------

    async def async_step_reconfigure(self, user_input=None):
        """Allow reconfiguring connection settings."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            if not await _test_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_RACK, DEFAULT_RACK),
                user_input.get(CONF_SLOT, DEFAULT_SLOT),
            ):
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **user_input},
                )
                return self.async_update_reload_and_abort(entry)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SiemensLogoOptionsFlow()


class SiemensLogoOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow to edit connection settings, entities and their addresses."""

    def __init__(self) -> None:
        self._connection_data: dict = {}
        self._entities: list[dict] = []

    async def async_step_init(self, user_input=None):
        """Step 1: Connection settings."""
        errors = {}

        if user_input is not None:
            if not await _test_connection(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_RACK, DEFAULT_RACK),
                user_input.get(CONF_SLOT, DEFAULT_SLOT),
            ):
                errors["base"] = "cannot_connect"
            else:
                self._connection_data = user_input
                return await self.async_step_entities()

        return self.async_show_form(
            step_id="init",
            data_schema=_connection_schema(self.config_entry.data),
            errors=errors,
        )

    async def async_step_entities(self, user_input=None):
        """Step 2: Edit entity list."""
        errors = {}
        current_entities = self.config_entry.data.get(CONF_ENTITIES, [])
        current_str = ",".join(f"{e['block']}{e['number']}" for e in current_entities)

        if user_input is not None:
            entities, error = _parse_entities(
                self._connection_data[CONF_MODEL],
                user_input[CONF_ENTITIES],
                current_entities,
            )
            if error:
                errors["base"] = error
            else:
                self._entities = entities
                return await self.async_step_addresses()

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {vol.Required(CONF_ENTITIES, default=current_str): str}
            ),
            errors=errors,
            description_placeholders={"example": "NI1,NI2,NQ1,AI1,Q1,M1"},
        )

    async def async_step_addresses(self, user_input=None):
        """Step 3: Confirm or override VM address per entity."""
        errors = {}
        if user_input is not None:
            try:
                entities = _apply_address_overrides(
                    self._connection_data[CONF_MODEL],
                    self._entities,
                    _flatten_section_input(user_input),
                )
            except (ValueError, KeyError) as err:
                errors["base"] = "invalid_address"
                _LOGGER.error("Invalid address: %s", err)
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        **self._connection_data,
                        CONF_ENTITIES: entities,
                    },
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="addresses",
            data_schema=_build_addresses_schema(self._entities),
            errors=errors,
        )
