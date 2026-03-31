"""Integration tests using a real snap7 S7 server (no physical PLC required).

The snap7 Server copies the registered buffer on startup, so all state is
managed by writing and reading via the client — no direct bytearray inspection.
"""
from __future__ import annotations

import time
from ctypes import c_char

import pytest
import pytest_socket

try:
    from snap7.server import Server
    from snap7.type import SrvArea
    HAS_REAL_SNAP7 = True
except (ImportError, ModuleNotFoundError):
    HAS_REAL_SNAP7 = False

pytestmark = pytest.mark.skipif(
    not HAS_REAL_SNAP7, reason="real snap7 library not installed"
)

if HAS_REAL_SNAP7:
    from siemens_logo import LogoConnection

# DB1 must cover all 0BA8 addresses (NAQ ends at ~1358)
_DB_SIZE = 1400
_TEST_PORT = 1102


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def s7_server():
    """Start a snap7 S7 server with DB1. Shared for the whole module."""
    # pytest-homeassistant-custom-component disables sockets in pytest_runtest_setup,
    # which runs before fixture setup. Re-enable here so the server socket can be created.
    pytest_socket.enable_socket()

    db_data = bytearray(_DB_SIZE)
    db_array = (c_char * _DB_SIZE).from_buffer(db_data)

    server = Server()
    server.register_area(SrvArea.DB, 1, db_array)
    server.start(tcp_port=_TEST_PORT)
    time.sleep(0.1)

    yield server

    server.stop()


@pytest.fixture(scope="module")
def conn(s7_server):
    """One persistent client connection for the whole module."""
    connection = LogoConnection("127.0.0.1", 0, 1, port=_TEST_PORT)
    connection.connect()
    yield connection
    connection.disconnect()


@pytest.fixture(autouse=True)
def reset_db(conn):
    """Write zeros to the entire DB1 before every test so state doesn't leak."""
    conn._client.db_write(1, 0, bytearray(_DB_SIZE))
    yield


# ---------------------------------------------------------------------------
# read_vm
# ---------------------------------------------------------------------------

class TestReadVm:
    def test_reads_zeros_after_reset(self, conn: LogoConnection) -> None:
        data = conn.read_vm(0, 4)
        assert data == bytearray(4)

    def test_reads_back_data_written_via_client(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 10, bytearray([0xAB, 0xCD]))
        data = conn.read_vm(10, 2)
        assert data[0] == 0xAB
        assert data[1] == 0xCD

    def test_reads_correct_slice(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 5, bytearray([0x01, 0x02, 0x03]))
        data = conn.read_vm(5, 3)
        assert list(data) == [0x01, 0x02, 0x03]

    def test_reads_high_vm_address(self, conn: LogoConnection) -> None:
        """Verify that upper-range addresses (e.g. NAI at 1262) are accessible."""
        conn._client.db_write(1, 1262, bytearray([0x12, 0x34]))
        data = conn.read_vm(1262, 2)
        assert data[0] == 0x12
        assert data[1] == 0x34


# ---------------------------------------------------------------------------
# write_vm_bool
# ---------------------------------------------------------------------------

class TestWriteVmBool:
    def test_sets_bit_to_true(self, conn: LogoConnection) -> None:
        conn.write_vm_bool(0, 0, True)
        data = conn.read_vm(0, 1)
        assert data[0] & (1 << 0)

    def test_sets_bit_to_false(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 0, bytearray([0xFF]))
        conn.write_vm_bool(0, 3, False)
        data = conn.read_vm(0, 1)
        assert not (data[0] & (1 << 3))

    def test_does_not_affect_adjacent_bits(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 0, bytearray([0b00000101]))  # bits 0 and 2
        conn.write_vm_bool(0, 1, True)
        data = conn.read_vm(0, 1)
        assert data[0] & (1 << 0), "bit 0 should still be set"
        assert data[0] & (1 << 1), "bit 1 should now be set"
        assert data[0] & (1 << 2), "bit 2 should still be set"

    def test_roundtrip_set_then_clear(self, conn: LogoConnection) -> None:
        conn.write_vm_bool(2, 5, True)
        assert conn.read_vm(2, 1)[0] & (1 << 5)
        conn.write_vm_bool(2, 5, False)
        assert not (conn.read_vm(2, 1)[0] & (1 << 5))

    def test_sets_bit_in_correct_byte(self, conn: LogoConnection) -> None:
        conn.write_vm_bool(3, 0, True)
        assert conn.read_vm(3, 1)[0] & 0x01
        assert conn.read_vm(2, 1)[0] == 0  # adjacent byte untouched
        assert conn.read_vm(4, 1)[0] == 0


# ---------------------------------------------------------------------------
# write_vm_int
# ---------------------------------------------------------------------------

class TestWriteVmInt:
    def test_writes_positive_value(self, conn: LogoConnection) -> None:
        conn.write_vm_int(1032, 1234)
        data = conn.read_vm(1032, 2)
        assert int.from_bytes(data, byteorder="big", signed=True) == 1234

    def test_writes_zero(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 1032, bytearray([0xFF, 0xFF]))
        conn.write_vm_int(1032, 0)
        data = conn.read_vm(1032, 2)
        assert int.from_bytes(data, byteorder="big", signed=True) == 0

    def test_writes_negative_value(self, conn: LogoConnection) -> None:
        conn.write_vm_int(1032, -500)
        data = conn.read_vm(1032, 2)
        assert int.from_bytes(data, byteorder="big", signed=True) == -500

    def test_writes_max_int16(self, conn: LogoConnection) -> None:
        conn.write_vm_int(1262, 32767)
        data = conn.read_vm(1262, 2)
        assert int.from_bytes(data, byteorder="big", signed=True) == 32767

    def test_does_not_affect_adjacent_bytes(self, conn: LogoConnection) -> None:
        conn._client.db_write(1, 1030, bytearray([0xAA]))
        conn._client.db_write(1, 1034, bytearray([0xBB]))
        conn.write_vm_int(1032, 999)
        assert conn.read_vm(1030, 1)[0] == 0xAA
        assert conn.read_vm(1034, 1)[0] == 0xBB


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_bool_write_then_read(self, conn: LogoConnection) -> None:
        conn.write_vm_bool(0, 2, True)
        data = conn.read_vm(0, 1)
        assert data[0] & (1 << 2)

    def test_int_write_then_read(self, conn: LogoConnection) -> None:
        conn.write_vm_int(1032, 4242)
        data = conn.read_vm(1032, 2)
        assert int.from_bytes(data, byteorder="big", signed=True) == 4242

    def test_multiple_entities_independent(self, conn: LogoConnection) -> None:
        """Writing one entity must not corrupt another."""
        conn.write_vm_bool(0, 0, True)   # NI1
        conn.write_vm_bool(0, 1, True)   # NI2
        conn.write_vm_int(1032, 750)     # AI1

        assert conn.read_vm(0, 1)[0] & (1 << 0), "NI1 should be set"
        assert conn.read_vm(0, 1)[0] & (1 << 1), "NI2 should be set"
        ai1 = conn.read_vm(1032, 2)
        assert int.from_bytes(ai1, byteorder="big", signed=True) == 750


# ---------------------------------------------------------------------------
# Reconnect — its own connection so the module-level conn is unaffected
# ---------------------------------------------------------------------------

class TestReconnect:
    def test_reconnects_after_disconnect(self, s7_server, socket_enabled) -> None:
        connection = LogoConnection("127.0.0.1", 0, 1, port=_TEST_PORT)
        connection.connect()
        connection._client.disconnect()
        # Next read should trigger _ensure_connected and succeed
        data = connection.read_vm(0, 1)
        assert isinstance(data, bytearray)
        connection.disconnect()
