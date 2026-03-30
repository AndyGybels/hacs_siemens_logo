"""Tests for siemens_logo const utilities."""
from __future__ import annotations

import pytest

from siemens_logo.const import (
    format_address,
    get_platform,
    get_vm_read_ranges,
    parse_address,
    parse_entity_string,
    resolve_address,
)


class TestResolveAddress:
    """Tests for resolve_address()."""

    def test_digital_block_bit_zero(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "NI", 1)
        assert byte_offset == 0
        assert bit_offset == 0

    def test_digital_block_second_bit(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "NI", 2)
        assert byte_offset == 0
        assert bit_offset == 1

    def test_digital_block_ninth_bit_wraps_byte(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "NI", 9)
        assert byte_offset == 1
        assert bit_offset == 0

    def test_digital_q_block(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "Q", 1)
        assert byte_offset == 1064
        assert bit_offset == 0

    def test_analog_block_returns_none_bit(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "AI", 1)
        assert byte_offset == 1032
        assert bit_offset is None

    def test_analog_block_second_channel(self) -> None:
        byte_offset, bit_offset = resolve_address("0BA8", "AI", 2)
        assert byte_offset == 1034
        assert bit_offset is None

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LOGO! model"):
            resolve_address("0BA9", "NI", 1)

    def test_unknown_block_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown block"):
            resolve_address("0BA8", "ZZ", 1)

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            resolve_address("0BA8", "NI", 65)

    def test_zero_number_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            resolve_address("0BA8", "NI", 0)


class TestFormatAddress:
    """Tests for format_address()."""

    def test_digital_formats_as_byte_dot_bit(self) -> None:
        assert format_address(0, 0) == "0.0"
        assert format_address(1, 7) == "1.7"

    def test_analog_formats_as_byte_only(self) -> None:
        assert format_address(1032, None) == "1032"


class TestParseAddress:
    """Tests for parse_address()."""

    def test_digital_parses_byte_dot_bit(self) -> None:
        assert parse_address("0.0", "digital") == (0, 0)
        assert parse_address("1.7", "digital") == (1, 7)

    def test_analog_parses_byte_only(self) -> None:
        assert parse_address("1032", "analog") == (1032, None)

    def test_digital_missing_dot_raises(self) -> None:
        with pytest.raises(ValueError, match="byte.bit"):
            parse_address("10", "digital")

    def test_digital_extra_parts_raises(self) -> None:
        with pytest.raises(ValueError, match="byte.bit"):
            parse_address("1.2.3", "digital")

    def test_digital_whitespace_stripped(self) -> None:
        assert parse_address("  0.0  ", "digital") == (0, 0)


class TestParseEntityString:
    """Tests for parse_entity_string()."""

    def test_ni_prefix(self) -> None:
        assert parse_entity_string("NI1") == ("NI", 1)

    def test_nai_prefix(self) -> None:
        assert parse_entity_string("NAI3") == ("NAI", 3)

    def test_lowercase_normalised(self) -> None:
        assert parse_entity_string("ni1") == ("NI", 1)

    def test_q_block(self) -> None:
        assert parse_entity_string("Q5") == ("Q", 5)

    def test_ai_block(self) -> None:
        assert parse_entity_string("AI2") == ("AI", 2)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_entity_string("UNKNOWN99")

    def test_no_number_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_entity_string("NI")


class TestGetPlatform:
    """Tests for get_platform()."""

    def test_ni_returns_switch(self) -> None:
        assert get_platform("NI") == "switch"

    def test_q_returns_binary_sensor(self) -> None:
        assert get_platform("Q") == "binary_sensor"

    def test_ai_returns_sensor(self) -> None:
        assert get_platform("AI") == "sensor"

    def test_nai_returns_number(self) -> None:
        assert get_platform("NAI") == "number"

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown block"):
            get_platform("ZZ")


class TestGetVmReadRanges:
    """Tests for get_vm_read_ranges()."""

    def test_empty_entities_returns_empty(self) -> None:
        assert get_vm_read_ranges([]) == []

    def test_single_digital_entity(self) -> None:
        entities = [{"byte_offset": 0, "bit_offset": 0}]
        ranges = get_vm_read_ranges(entities)
        assert len(ranges) == 1
        start, size = ranges[0]
        assert start == 0
        assert size == 1  # 1 byte for a digital entity at byte 0

    def test_single_analog_entity(self) -> None:
        entities = [{"byte_offset": 1032, "bit_offset": None}]
        ranges = get_vm_read_ranges(entities)
        assert len(ranges) == 1
        start, size = ranges[0]
        assert start == 1032
        assert size == 2  # analog = 2 bytes

    def test_chunks_large_range(self) -> None:
        entities = [
            {"byte_offset": 0, "bit_offset": 0},
            {"byte_offset": 500, "bit_offset": None},
        ]
        ranges = get_vm_read_ranges(entities)
        # Total span is 502 bytes, max chunk is 200
        assert len(ranges) > 1
        starts = [r[0] for r in ranges]
        assert starts[0] == 0

    def test_ranges_cover_all_entities(self) -> None:
        entities = [
            {"byte_offset": 0, "bit_offset": 0},
            {"byte_offset": 1032, "bit_offset": None},
        ]
        ranges = get_vm_read_ranges(entities)
        vm_start = ranges[0][0]
        vm_end = max(s + sz for s, sz in ranges)
        for e in entities:
            span = 1 if e["bit_offset"] is not None else 2
            assert e["byte_offset"] >= vm_start
            assert e["byte_offset"] + span <= vm_end
