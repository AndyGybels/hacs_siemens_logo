"""Tests for the Siemens LOGO! config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from siemens_logo.config_flow import (
    SiemensLogoConfigFlow,
    SiemensLogoOptionsFlow,
    _apply_address_overrides,
    _build_addresses_schema,
    _parse_entities,
)
from siemens_logo.const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_MODEL,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
)

from .conftest import MOCK_ENTRY_DATA


# ---------------------------------------------------------------------------
# Helper to build a fake connection_data dict
# ---------------------------------------------------------------------------
def _conn_data(**overrides):
    base = {
        "host": "192.168.1.100",
        "rack": 0,
        "slot": 1,
        "model": "0BA8",
        "scan_interval": 500,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _parse_entities
# ---------------------------------------------------------------------------
class TestParseEntities:
    def test_parses_single_ni(self) -> None:
        entities, error = _parse_entities("0BA8", "NI1", [])
        assert error is None
        assert len(entities) == 1
        assert entities[0]["block"] == "NI"
        assert entities[0]["number"] == 1
        assert entities[0]["platform"] == "switch"

    def test_parses_multiple_mixed(self) -> None:
        entities, error = _parse_entities("0BA8", "NI1,Q1,AI1", [])
        assert error is None
        assert len(entities) == 3
        platforms = {e["block"]: e["platform"] for e in entities}
        assert platforms["NI"] == "switch"
        assert platforms["Q"] == "binary_sensor"
        assert platforms["AI"] == "sensor"

    def test_invalid_entity_returns_error(self) -> None:
        entities, error = _parse_entities("0BA8", "INVALID99", [])
        assert error == "invalid_entity"
        assert entities == []

    def test_preserves_existing_overrides(self) -> None:
        existing = [
            {
                "block": "NI",
                "number": 1,
                "platform": "button",
                "name": "My Button",
                "byte_offset": 5,
                "bit_offset": 3,
            }
        ]
        entities, error = _parse_entities("0BA8", "NI1", existing)
        assert error is None
        assert entities[0]["byte_offset"] == 5
        assert entities[0]["bit_offset"] == 3
        assert entities[0]["platform"] == "button"

    def test_whitespace_and_empty_parts_ignored(self) -> None:
        entities, error = _parse_entities("0BA8", " NI1 , , NI2 ", [])
        assert error is None
        assert len(entities) == 2


# ---------------------------------------------------------------------------
# _build_addresses_schema
# ---------------------------------------------------------------------------
class TestBuildAddressesSchema:
    def test_ni_entity_has_push_field(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        schema = _build_addresses_schema(entities)
        outer_keys = [k.schema for k in schema.schema]
        assert "NI1" in outer_keys
        # Inner fields live inside the section
        ni1_key = next(k for k in schema.schema if k.schema == "NI1")
        inner_keys = [k.schema for k in schema.schema[ni1_key].schema.schema]
        assert "NI1" in inner_keys
        assert "NI1_name" in inner_keys
        assert "NI1_unique_id" in inner_keys
        assert "NI1_push" in inner_keys

    def test_q_entity_has_no_push_field(self) -> None:
        entities = [
            {
                "block": "Q",
                "number": 1,
                "platform": "binary_sensor",
                "name": "LOGO Q1",
                "byte_offset": 1064,
                "bit_offset": 0,
            }
        ]
        schema = _build_addresses_schema(entities)
        keys = [k.schema for k in schema.schema]
        assert "Q1" in keys
        assert "Q1_push" not in keys

    def test_prefills_existing_address(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "My Switch",
                "byte_offset": 3,
                "bit_offset": 5,
            }
        ]
        schema = _build_addresses_schema(entities)
        ni1_key = next(k for k in schema.schema if k.schema == "NI1")
        inner_schema = schema.schema[ni1_key].schema
        defaults = {k.schema: k.default() for k in inner_schema.schema}
        assert defaults["NI1"] == "3.5"
        assert defaults["NI1_name"] == "My Switch"


# ---------------------------------------------------------------------------
# _apply_address_overrides
# ---------------------------------------------------------------------------
class TestApplyAddressOverrides:
    def test_applies_digital_address(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        user_input = {"NI1": "2.3", "NI1_name": "Renamed", "NI1_unique_id": "", "NI1_push": False}
        result = _apply_address_overrides("0BA8", entities, user_input)
        assert result[0]["byte_offset"] == 2
        assert result[0]["bit_offset"] == 3
        assert result[0]["name"] == "Renamed"
        assert result[0]["unique_id"] is None

    def test_push_flag_sets_button_platform(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        user_input = {"NI1": "0.0", "NI1_name": "Pulse", "NI1_unique_id": "", "NI1_push": True}
        result = _apply_address_overrides("0BA8", entities, user_input)
        assert result[0]["platform"] == "button"

    def test_no_push_flag_keeps_original_platform(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        user_input = {"NI1": "0.0", "NI1_name": "Switch", "NI1_unique_id": "uid1", "NI1_push": False}
        result = _apply_address_overrides("0BA8", entities, user_input)
        assert result[0]["platform"] == "switch"
        assert result[0]["unique_id"] == "uid1"

    def test_invalid_address_raises(self) -> None:
        entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        user_input = {"NI1": "not_valid", "NI1_name": "N", "NI1_unique_id": "", "NI1_push": False}
        with pytest.raises((ValueError, Exception)):
            _apply_address_overrides("0BA8", entities, user_input)


# ---------------------------------------------------------------------------
# Config flow (unit-level, without HA hass fixture)
# ---------------------------------------------------------------------------
class TestConfigFlowStepUser:
    """Test async_step_user with patched connection test."""

    @pytest.fixture
    def flow(self) -> SiemensLogoConfigFlow:
        flow = SiemensLogoConfigFlow()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=None)
        flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "user"})
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        # context is a read-only mappingproxy when instantiated outside HA's flow manager
        flow.async_set_unique_id = AsyncMock(return_value=None)
        flow._abort_if_unique_id_configured = MagicMock()
        return flow

    async def test_shows_form_on_first_call(self, flow: SiemensLogoConfigFlow) -> None:
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await flow.async_step_user(None)
        flow.async_show_form.assert_called_once()
        assert result["step_id"] == "user"

    async def test_connection_error_sets_error(self, flow: SiemensLogoConfigFlow) -> None:
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=False,
        ):
            flow.async_step_entities = AsyncMock(return_value={"type": "form", "step_id": "entities"})
            result = await flow.async_step_user(_conn_data())

        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"].get("base") == "cannot_connect"

    async def test_valid_input_advances_to_entities(self, flow: SiemensLogoConfigFlow) -> None:
        flow.async_step_entities = AsyncMock(return_value={"type": "form", "step_id": "entities"})
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await flow.async_step_user(_conn_data())

        flow.async_step_entities.assert_called_once()


class TestConfigFlowStepEntities:
    """Test async_step_entities."""

    @pytest.fixture
    def flow(self) -> SiemensLogoConfigFlow:
        flow = SiemensLogoConfigFlow()
        flow._connection_data = _conn_data()
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "entities"})
        return flow

    async def test_shows_form_on_first_call(self, flow: SiemensLogoConfigFlow) -> None:
        result = await flow.async_step_entities(None)
        flow.async_show_form.assert_called_once()

    async def test_invalid_entity_shows_error(self, flow: SiemensLogoConfigFlow) -> None:
        flow.async_step_addresses = AsyncMock(return_value={})
        result = await flow.async_step_entities({CONF_ENTITIES: "BADBLOCK99"})
        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"].get("base") == "invalid_entity"

    async def test_valid_entities_advances(self, flow: SiemensLogoConfigFlow) -> None:
        flow.async_step_addresses = AsyncMock(return_value={"type": "form", "step_id": "addresses"})
        result = await flow.async_step_entities({CONF_ENTITIES: "NI1,Q1"})
        flow.async_step_addresses.assert_called_once()
        assert len(flow._entities) == 2


class TestConfigFlowStepAddresses:
    """Test async_step_addresses."""

    @pytest.fixture
    def flow(self) -> SiemensLogoConfigFlow:
        flow = SiemensLogoConfigFlow()
        flow._connection_data = _conn_data()
        flow._entities = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "LOGO NI1",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "addresses"})
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        return flow

    async def test_shows_form_on_first_call(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_addresses(None)
        flow.async_show_form.assert_called_once()

    async def test_valid_input_creates_entry(self, flow: SiemensLogoConfigFlow) -> None:
        user_input = {"NI1": "0.0", "NI1_name": "Switch", "NI1_unique_id": "", "NI1_push": False}
        await flow.async_step_addresses(user_input)
        flow.async_create_entry.assert_called_once()
        _, kwargs = flow.async_create_entry.call_args
        entities = kwargs["data"][CONF_ENTITIES]
        assert len(entities) == 1
        assert entities[0]["byte_offset"] == 0
        assert entities[0]["bit_offset"] == 0

    async def test_invalid_address_shows_error(self, flow: SiemensLogoConfigFlow) -> None:
        user_input = {"NI1": "bad", "NI1_name": "Switch", "NI1_unique_id": "", "NI1_push": False}
        await flow.async_step_addresses(user_input)
        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"].get("base") == "invalid_address"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------
class TestOptionsFlow:
    """Test SiemensLogoOptionsFlow."""

    @pytest.fixture
    def flow(self) -> SiemensLogoOptionsFlow:
        flow = SiemensLogoOptionsFlow()
        config_entry = MagicMock()
        config_entry.data = MOCK_ENTRY_DATA.copy()
        # Simulate the HA property by attaching it
        type(flow).config_entry = property(lambda self: config_entry)
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        return flow

    async def test_init_shows_connection_form(self, flow: SiemensLogoOptionsFlow) -> None:
        result = await flow.async_step_init(None)
        flow.async_show_form.assert_called_once()

    async def test_connection_failure_shows_error(self, flow: SiemensLogoOptionsFlow) -> None:
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await flow.async_step_init(_conn_data())
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"].get("base") == "cannot_connect"

    async def test_valid_connection_advances_to_entities(self, flow: SiemensLogoOptionsFlow) -> None:
        flow.async_step_entities = AsyncMock(return_value={"type": "form"})
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await flow.async_step_init(_conn_data())
        flow.async_step_entities.assert_called_once()

    async def test_entities_prefilled_from_current_config(self, flow: SiemensLogoOptionsFlow) -> None:
        await flow.async_step_entities(None)
        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        # The schema should have a default based on current entities
        schema = kwargs["data_schema"]
        defaults = {k.schema: k.default() for k in schema.schema}
        # Current entry has NI1, NI2, Q1, AI1
        assert "NI1" in defaults[CONF_ENTITIES]


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------
class TestReconfigureFlow:
    """Test async_step_reconfigure."""

    @pytest.fixture
    def flow(self) -> SiemensLogoConfigFlow:
        flow = SiemensLogoConfigFlow()
        entry = MagicMock()
        entry.data = _conn_data()
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "reconfigure"})
        flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})
        return flow

    async def test_shows_prefilled_form(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_reconfigure(None)
        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["step_id"] == "reconfigure"

    async def test_connection_failure_shows_error(self, flow: SiemensLogoConfigFlow) -> None:
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await flow.async_step_reconfigure(_conn_data())
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"].get("base") == "cannot_connect"

    async def test_valid_input_updates_and_aborts(self, flow: SiemensLogoConfigFlow) -> None:
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await flow.async_step_reconfigure(_conn_data())
        flow.async_update_reload_and_abort.assert_called_once()

    async def test_updates_entry_data(self, flow: SiemensLogoConfigFlow) -> None:
        new_data = _conn_data(host="10.0.0.2", scan_interval=500)
        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await flow.async_step_reconfigure(new_data)
        flow.hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = flow.hass.config_entries.async_update_entry.call_args
        assert kwargs["data"]["host"] == "10.0.0.2"
        assert kwargs["data"]["scan_interval"] == 500


# ---------------------------------------------------------------------------
# Duplicate entry prevention
# ---------------------------------------------------------------------------
class TestUniqueConfigEntry:
    """Test that the same device cannot be added twice."""

    async def test_aborts_if_unique_id_already_configured(self) -> None:
        flow = SiemensLogoConfigFlow()
        flow.hass = MagicMock()

        # Simulate async_set_unique_id succeeding (no duplicate)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_step_entities = AsyncMock(return_value={"type": "form"})
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await flow.async_step_user(_conn_data())

        flow.async_set_unique_id.assert_called_once_with("192.168.1.100")
        flow._abort_if_unique_id_configured.assert_called_once()

    async def test_unique_id_set_to_host(self) -> None:

        flow = SiemensLogoConfigFlow()
        flow.hass = MagicMock()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_step_entities = AsyncMock(return_value={"type": "form"})
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        with patch(
            "siemens_logo.config_flow._test_connection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await flow.async_step_user(_conn_data(host="10.0.0.99"))

        flow.async_set_unique_id.assert_called_once_with("10.0.0.99")


# ---------------------------------------------------------------------------
# YAML import flow
# ---------------------------------------------------------------------------
def _import_data(**overrides) -> dict:
    base = {
        CONF_HOST: "192.168.1.50",
        CONF_RACK: DEFAULT_RACK,
        CONF_SLOT: DEFAULT_SLOT,
        CONF_MODEL: "0BA8",
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_ENTITIES: [{"block": "NI1", "name": "Pump"}],
    }
    base.update(overrides)
    return base


class TestImportFlow:
    """Test async_step_import (configuration.yaml)."""

    @pytest.fixture
    def flow(self) -> SiemensLogoConfigFlow:
        flow = SiemensLogoConfigFlow()
        flow.hass = MagicMock()
        flow.async_set_unique_id = AsyncMock(return_value=None)
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        return flow

    async def test_creates_entry_with_correct_host(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        flow.async_create_entry.assert_called_once()
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_HOST] == "192.168.1.50"

    async def test_creates_entry_with_correct_title(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["title"] == "LOGO! 192.168.1.50"

    async def test_resolves_default_vm_address(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        _, kwargs = flow.async_create_entry.call_args
        entity = kwargs["data"][CONF_ENTITIES][0]
        # NI1 on 0BA8: byte 0, bit 0
        assert entity["byte_offset"] == 0
        assert entity["bit_offset"] == 0

    async def test_applies_address_override(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(
            entities=[{"block": "NI1", "name": "Pump", "address": "3.5"}]
        )
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        entity = kwargs["data"][CONF_ENTITIES][0]
        assert entity["byte_offset"] == 3
        assert entity["bit_offset"] == 5

    async def test_push_button_flag_sets_button_platform(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(
            entities=[{"block": "NI1", "name": "Reset", "push_button": True}]
        )
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        entity = kwargs["data"][CONF_ENTITIES][0]
        assert entity["platform"] == "button"

    async def test_no_push_button_flag_uses_switch_platform(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        _, kwargs = flow.async_create_entry.call_args
        entity = kwargs["data"][CONF_ENTITIES][0]
        assert entity["platform"] == "switch"

    async def test_carries_name(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_ENTITIES][0]["name"] == "Pump"

    async def test_default_name_when_omitted(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(entities=[{"block": "NI1"}])
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_ENTITIES][0]["name"] == "LOGO NI1"

    async def test_carries_unique_id(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(
            entities=[{"block": "NI1", "unique_id": "my_pump"}]
        )
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_ENTITIES][0]["unique_id"] == "my_pump"

    async def test_unique_id_none_when_omitted(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_ENTITIES][0]["unique_id"] is None

    async def test_preserves_connection_fields(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(**{CONF_RACK: 1, CONF_SLOT: 2, CONF_SCAN_INTERVAL: 500})
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        assert kwargs["data"][CONF_RACK] == 1
        assert kwargs["data"][CONF_SLOT] == 2
        assert kwargs["data"][CONF_SCAN_INTERVAL] == 500

    async def test_multiple_entities_all_resolved(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(
            entities=[
                {"block": "NI1", "name": "Pump"},
                {"block": "Q1", "name": "Motor"},
                {"block": "AI1", "name": "Level"},
            ]
        )
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        entities = kwargs["data"][CONF_ENTITIES]
        assert len(entities) == 3
        blocks = [e["block"] for e in entities]
        assert blocks == ["NI", "Q", "AI"]

    async def test_invalid_block_aborts(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(entities=[{"block": "BADBLOCK99"}])
        await flow.async_step_import(data)
        flow.async_abort.assert_called_once_with(reason="invalid_entity")
        flow.async_create_entry.assert_not_called()

    async def test_sets_unique_id_to_host(self, flow: SiemensLogoConfigFlow) -> None:
        await flow.async_step_import(_import_data())
        flow.async_set_unique_id.assert_called_once_with("192.168.1.50")

    async def test_aborts_if_already_configured(self, flow: SiemensLogoConfigFlow) -> None:
        flow._abort_if_unique_id_configured.side_effect = Exception("already configured")
        with pytest.raises(Exception, match="already configured"):
            await flow.async_step_import(_import_data())
        flow.async_create_entry.assert_not_called()

    async def test_passes_updates_when_entry_exists(self, flow: SiemensLogoConfigFlow) -> None:
        """Existing entry receives updated data so YAML changes are picked up on restart."""
        await flow.async_step_import(_import_data())
        _, kwargs = flow._abort_if_unique_id_configured.call_args
        assert "updates" in kwargs
        assert CONF_ENTITIES in kwargs["updates"]["data"]
        assert kwargs["updates"]["data"][CONF_HOST] == "192.168.1.50"

    async def test_analog_entity_has_no_bit_offset(self, flow: SiemensLogoConfigFlow) -> None:
        data = _import_data(entities=[{"block": "AI1", "name": "Level"}])
        await flow.async_step_import(data)
        _, kwargs = flow.async_create_entry.call_args
        entity = kwargs["data"][CONF_ENTITIES][0]
        assert entity["bit_offset"] is None
        assert entity["byte_offset"] == 1032  # AI1 on 0BA8
