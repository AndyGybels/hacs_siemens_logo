"""Test configuration and fixtures for siemens_logo."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Make `siemens_logo` importable (custom_components is one level up)
# ---------------------------------------------------------------------------
_CUSTOM_COMPONENTS = str(Path(__file__).parents[1] / "custom_components")
if _CUSTOM_COMPONENTS not in sys.path:
    sys.path.insert(0, _CUSTOM_COMPONENTS)

# ---------------------------------------------------------------------------
# Stub out `snap7` before any integration module is imported so that tests
# can run without the native library installed.
# ---------------------------------------------------------------------------
if "snap7" not in sys.modules:
    _snap7 = types.ModuleType("snap7")
    _snap7_client = types.ModuleType("snap7.client")
    _snap7_util = types.ModuleType("snap7.util")

    _snap7_util.get_bool = MagicMock(return_value=False)
    _snap7_util.set_bool = MagicMock()
    _snap7_util.get_int = MagicMock(return_value=0)
    _snap7_util.set_int = MagicMock()

    _snap7_client.Client = MagicMock

    _snap7.client = _snap7_client
    _snap7.util = _snap7_util

    sys.modules["snap7"] = _snap7
    sys.modules["snap7.client"] = _snap7_client
    sys.modules["snap7.util"] = _snap7_util


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MOCK_ENTRY_DATA = {
    "host": "192.168.1.100",
    "rack": 0,
    "slot": 1,
    "model": "0BA8",
    "scan_interval": 1000,
    "entities": [
        {
            "block": "NI",
            "number": 1,
            "platform": "switch",
            "name": "LOGO NI1",
            "byte_offset": 0,
            "bit_offset": 0,
            "unique_id": None,
        },
        {
            "block": "NI",
            "number": 2,
            "platform": "button",
            "name": "LOGO NI2",
            "byte_offset": 0,
            "bit_offset": 1,
            "unique_id": "my_button",
        },
        {
            "block": "Q",
            "number": 1,
            "platform": "binary_sensor",
            "name": "LOGO Q1",
            "byte_offset": 1064,
            "bit_offset": 0,
            "unique_id": None,
        },
        {
            "block": "AI",
            "number": 1,
            "platform": "sensor",
            "name": "LOGO AI1",
            "byte_offset": 1032,
            "bit_offset": None,
            "unique_id": None,
        },
    ],
}


@pytest.fixture
def mock_snap7_client():
    """Return a mock snap7 Client instance."""
    client = MagicMock()
    client.get_connected.return_value = True
    client.db_read.return_value = bytearray(4)
    client.db_write.return_value = None
    client.connect.return_value = None
    client.disconnect.return_value = None
    return client
