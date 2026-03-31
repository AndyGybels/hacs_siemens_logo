"""Tests for the Siemens LOGO! config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.siemens_logo.config_flow import (
    _apply_address_overrides,
    _build_addresses_schema,
    _parse_entities,
)
from custom_components.siemens_logo.const import (
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
)

from .conftest import MOCK_ENTRY_DATA

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_setup_entry() -> None:
    """Prevent real PLC setup during config flow tests."""
    with patch(
        "custom_components.siemens_logo.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_connection() -> None:
    """Prevent real TCP connections during config flow tests."""
    with patch(
        "custom_components.siemens_logo.config_flow._test_connection",
        new=AsyncMock(return_value=True),
    ):
        yield


def _conn_input(**overrides: object) -> dict:
    """Build a minimal valid user-step input dict."""
    base: dict = {
        CONF_HOST: "192.168.1.50",
        CONF_RACK: DEFAULT_RACK,
        CONF_SLOT: DEFAULT_SLOT,
        CONF_MODEL: "0BA8",
        CONF_SCAN_INTERVAL: 1000,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pure unit tests for helper functions (no hass required)
# ---------------------------------------------------------------------------


class TestParseEntities:
    """Unit tests for _parse_entities."""

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

    def test_preserves_existing_name(self) -> None:
        existing = [
            {
                "block": "NI",
                "number": 1,
                "platform": "switch",
                "name": "My Custom Name",
                "byte_offset": 0,
                "bit_offset": 0,
            }
        ]
        entities, error = _parse_entities("0BA8", "NI1", existing)
        assert error is None
        assert entities[0]["name"] == "My Custom Name"

    def test_whitespace_and_empty_parts_ignored(self) -> None:
        entities, error = _parse_entities("0BA8", " NI1 , , NI2 ", [])
        assert error is None
        assert len(entities) == 2


class TestBuildAddressesSchema:
    """Unit tests for _build_addresses_schema."""

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


class TestApplyAddressOverrides:
    """Unit tests for _apply_address_overrides."""

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
# User flow — 3-step setup with real HA infrastructure
# ---------------------------------------------------------------------------


class TestUserFlow:
    """Config flow tests using real HomeAssistant and the HA flow manager."""

    async def test_shows_user_form_on_init(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    async def test_connection_failure_shows_error(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        with patch(
            "custom_components.siemens_logo.config_flow._test_connection",
            new=AsyncMock(return_value=False),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _conn_input()
            )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_advances_to_entities_after_connection(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"

    async def test_invalid_entity_shows_error(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "BADBLOCK99"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        assert result["errors"]["base"] == "invalid_entity"

    async def test_advances_to_addresses_after_entities(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "addresses"

    async def test_invalid_address_shows_error(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"NI1": {"NI1": "not_valid", "NI1_name": "Pump", "NI1_unique_id": "", "NI1_push": False}},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "addresses"
        assert result["errors"]["base"] == "invalid_address"

    async def test_complete_flow_creates_entry(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"NI1": {"NI1": "0.0", "NI1_name": "Pump", "NI1_unique_id": "", "NI1_push": False}},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "192.168.1.50"
        assert result["data"][CONF_ENTITIES][0]["name"] == "Pump"
        assert result["data"][CONF_ENTITIES][0]["byte_offset"] == 0
        assert result["data"][CONF_ENTITIES][0]["bit_offset"] == 0

    async def test_push_flag_stored_as_button_platform(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"NI1": {"NI1": "0.0", "NI1_name": "Reset", "NI1_unique_id": "", "NI1_push": True}},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["platform"] == "button"

    async def test_duplicate_host_aborts(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={**MOCK_ENTRY_DATA, CONF_HOST: "192.168.1.50"},
            unique_id="192.168.1.50",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input()
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_unique_id_set_to_host(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input(host="10.0.0.99")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"NI1": {"NI1": "0.0", "NI1_name": "Switch", "NI1_unique_id": "", "NI1_push": False}},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = hass.config_entries.async_get_entry(result["result"].entry_id)
        assert entry.unique_id == "10.0.0.99"


# ---------------------------------------------------------------------------
# YAML import flow
# ---------------------------------------------------------------------------


def _import_data(**overrides: object) -> dict:
    """Build a minimal valid import data dict."""
    base: dict = {
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
    """YAML import flow tests (configuration.yaml → async_step_import)."""

    async def test_creates_entry_with_correct_host(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "192.168.1.50"

    async def test_creates_entry_with_correct_title(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "LOGO! 192.168.1.50"

    async def test_resolves_default_vm_address(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entity = result["data"][CONF_ENTITIES][0]
        assert entity["byte_offset"] == 0  # NI1 on 0BA8: byte 0, bit 0
        assert entity["bit_offset"] == 0

    async def test_applies_address_override(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "NI1", "name": "Pump", "address": "3.5"}]),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entity = result["data"][CONF_ENTITIES][0]
        assert entity["byte_offset"] == 3
        assert entity["bit_offset"] == 5

    async def test_push_button_flag_sets_button_platform(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "NI1", "name": "Reset", "push_button": True}]),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["platform"] == "button"

    async def test_no_push_button_flag_uses_switch_platform(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["platform"] == "switch"

    async def test_carries_entity_name(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["name"] == "Pump"

    async def test_default_name_when_omitted(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "NI1"}]),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["name"] == "LOGO NI1"

    async def test_carries_unique_id(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "NI1", "unique_id": "my_pump"}]),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["unique_id"] == "my_pump"

    async def test_unique_id_none_when_omitted(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ENTITIES][0]["unique_id"] is None

    async def test_multiple_entities_all_resolved(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(
                entities=[
                    {"block": "NI1", "name": "Pump"},
                    {"block": "Q1", "name": "Motor"},
                    {"block": "AI1", "name": "Level"},
                ]
            ),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entities = result["data"][CONF_ENTITIES]
        assert len(entities) == 3
        assert [e["block"] for e in entities] == ["NI", "Q", "AI"]

    async def test_analog_entity_has_no_bit_offset(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "AI1", "name": "Level"}]),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entity = result["data"][CONF_ENTITIES][0]
        assert entity["bit_offset"] is None
        assert entity["byte_offset"] == 1032  # AI1 on 0BA8

    async def test_invalid_block_aborts(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "BADBLOCK99"}]),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "invalid_entity"

    async def test_existing_entry_updated_on_reimport(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        """Importing the same host again must update the existing entry (YAML change picked up on restart)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=_import_data(entities=[{"block": "NI1", "name": "Old Name"}]),
            unique_id="192.168.1.50",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(entities=[{"block": "NI1", "name": "New Name"}, {"block": "Q1"}]),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        # The existing entry's data must have been updated
        updated = hass.config_entries.async_get_entry(entry.entry_id)
        assert len(updated.data[CONF_ENTITIES]) == 2
        assert updated.data[CONF_ENTITIES][0]["name"] == "New Name"

    async def test_existing_entry_scan_interval_updated(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> None:
        """Changed scan_interval in YAML must reach the existing entry on restart."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=_import_data(**{CONF_SCAN_INTERVAL: 1000}),
            unique_id="192.168.1.50",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=_import_data(**{CONF_SCAN_INTERVAL: 250}),
        )
        updated = hass.config_entries.async_get_entry(entry.entry_id)
        assert updated.data[CONF_SCAN_INTERVAL] == 250


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    """Options flow tests using real HA infrastructure."""

    @pytest.fixture
    async def loaded_entry(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> MockConfigEntry:
        """Add a config entry to hass and set it up."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_ENTRY_DATA.copy(),
            unique_id="192.168.1.100",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    async def test_shows_connection_form_on_init(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
    ) -> None:
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_connection_failure_shows_error(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
    ) -> None:
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        with patch(
            "custom_components.siemens_logo.config_flow._test_connection",
            new=AsyncMock(return_value=False),
        ):
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], _conn_input(host="192.168.1.100")
            )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_valid_connection_advances_to_entities(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], _conn_input(host="192.168.1.100")
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"

    async def test_entities_step_prefills_current_config(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], _conn_input(host="192.168.1.100")
        )
        assert result["type"] is FlowResultType.FORM
        # Default entities string should include blocks from current entry
        defaults = {k.schema: k.default() for k in result["data_schema"].schema}
        assert "NI1" in defaults[CONF_ENTITIES]

    async def test_complete_options_flow_updates_entry(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], _conn_input(host="192.168.1.100", scan_interval=500)
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_ENTITIES: "NI1"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"NI1": {"NI1": "0.0", "NI1_name": "Motor", "NI1_unique_id": "", "NI1_push": False}},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        updated = hass.config_entries.async_get_entry(loaded_entry.entry_id)
        assert updated.data[CONF_SCAN_INTERVAL] == 500
        assert updated.data[CONF_ENTITIES][0]["name"] == "Motor"


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


class TestReconfigureFlow:
    """Reconfigure flow tests using real HA infrastructure."""

    @pytest.fixture
    async def loaded_entry(
        self,
        hass: HomeAssistant,
        mock_setup_entry: None,
    ) -> MockConfigEntry:
        """Add a config entry to hass and set it up."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_ENTRY_DATA.copy(),
            unique_id="192.168.1.100",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    async def test_shows_prefilled_form(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": loaded_entry.entry_id},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    async def test_connection_failure_shows_error(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": loaded_entry.entry_id},
        )
        with patch(
            "custom_components.siemens_logo.config_flow._test_connection",
            new=AsyncMock(return_value=False),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _conn_input(host="192.168.1.100")
            )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_valid_input_updates_and_aborts(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": loaded_entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input(host="10.0.0.2", scan_interval=500)
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

    async def test_updates_entry_host_and_scan_interval(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        mock_connection: None,
    ) -> None:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": loaded_entry.entry_id},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], _conn_input(host="10.0.0.2", scan_interval=500)
        )
        updated = hass.config_entries.async_get_entry(loaded_entry.entry_id)
        assert updated.data[CONF_HOST] == "10.0.0.2"
        assert updated.data[CONF_SCAN_INTERVAL] == 500
