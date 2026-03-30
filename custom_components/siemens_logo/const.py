"""Constants for the Siemens LOGO! integration."""

DOMAIN = "siemens_logo"

CONF_HOST = "host"
CONF_RACK = "rack"
CONF_SLOT = "slot"
CONF_MODEL = "model"
CONF_ENTITIES = "entities"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_SCAN_INTERVAL = 1000  # milliseconds
MIN_SCAN_INTERVAL = 100  # milliseconds

# VM address maps per LOGO! model
# Each block: start byte in VM, max count, type (digital=bit, analog=word)
VM_MAPS = {
    "0BA8": {
        "I":   {"start": 1024, "count": 24, "type": "digital"},
        "Q":   {"start": 1064, "count": 20, "type": "digital"},
        "M":   {"start": 1104, "count": 64, "type": "digital"},
        "NI":  {"start": 0,    "count": 64, "type": "digital"},
        "NQ":  {"start": 1254, "count": 64, "type": "digital"},
        "AI":  {"start": 1032, "count": 8,  "type": "analog"},
        "AQ":  {"start": 1072, "count": 8,  "type": "analog"},
        "NAI": {"start": 1262, "count": 32, "type": "analog"},
        "NAQ": {"start": 1326, "count": 16, "type": "analog"},
    },
}

# Which blocks are writable from external clients
WRITABLE_DIGITAL = {"NI"}
WRITABLE_ANALOG = {"NAI"}

# Platform mapping based on block name
PLATFORM_MAP = {
    "I": "binary_sensor",
    "Q": "binary_sensor",
    "M": "binary_sensor",
    "NI": "switch",
    "NQ": "binary_sensor",
    "AI": "sensor",
    "AQ": "sensor",
    "NAI": "number",
    "NAQ": "sensor",
}

PLATFORMS = ["switch", "binary_sensor", "sensor", "number", "button"]

BUTTON_PULSE_MS = 500  # milliseconds the bit is held high for push buttons


def resolve_address(model: str, block_name: str, block_number: int):
    """Resolve a block reference to (byte_offset, bit_offset).

    Returns (byte_offset, bit_offset) for digital, (byte_offset, None) for analog.
    """
    vm_map = VM_MAPS.get(model)
    if vm_map is None:
        raise ValueError(f"Unknown LOGO! model: {model}")

    block = vm_map.get(block_name)
    if block is None:
        raise ValueError(f"Unknown block: {block_name}")

    if block_number < 1 or block_number > block["count"]:
        raise ValueError(
            f"{block_name}{block_number} out of range (max {block_name}{block['count']})"
        )

    if block["type"] == "digital":
        byte_offset = block["start"] + (block_number - 1) // 8
        bit_offset = (block_number - 1) % 8
        return byte_offset, bit_offset
    else:
        return block["start"] + (block_number - 1) * 2, None


def format_address(byte_offset: int, bit_offset: int | None) -> str:
    """Format a VM address as a string (e.g. '0.0' or '1032')."""
    if bit_offset is not None:
        return f"{byte_offset}.{bit_offset}"
    return str(byte_offset)


def parse_address(addr_str: str, block_type: str) -> tuple[int, int | None]:
    """Parse an address string into (byte_offset, bit_offset).

    Digital: '0.0' → (0, 0). Analog: '1032' → (1032, None).
    """
    addr_str = addr_str.strip()
    if block_type == "digital":
        parts = addr_str.split(".")
        if len(parts) != 2:
            raise ValueError(f"Digital address must be 'byte.bit', got: {addr_str!r}")
        return int(parts[0]), int(parts[1])
    else:
        return int(addr_str), None


def get_vm_read_ranges(entities: list[dict]):
    """Compute VM read ranges from a list of entity configs (each has byte_offset).

    Returns a list of (start, size) tuples chunked to fit within PDU limits.
    """
    if not entities:
        return []

    offsets = [e["byte_offset"] for e in entities]
    vm_start = min(offsets)
    # For digital blocks the range is 1 byte per entity offset; analog is 2.
    # We just span the full range from min to max+2 to be safe.
    vm_end = max(
        e["byte_offset"] + (1 if e.get("bit_offset") is not None else 2)
        for e in entities
    )

    max_chunk = 200
    ranges = []
    offset = vm_start
    while offset < vm_end:
        chunk_size = min(max_chunk, vm_end - offset)
        ranges.append((offset, chunk_size))
        offset += chunk_size

    return ranges


def get_platform(block_name: str) -> str:
    """Get the HA platform for a block name."""
    platform = PLATFORM_MAP.get(block_name)
    if platform is None:
        raise ValueError(f"Unknown block: {block_name}")
    return platform


def parse_entity_string(entity_str: str):
    """Parse 'NI1' → ('NI', 1)."""
    entity_str = entity_str.strip().upper()
    for prefix_len in (3, 2, 1):
        prefix = entity_str[:prefix_len]
        suffix = entity_str[prefix_len:]
        if prefix in PLATFORM_MAP and suffix.isdigit():
            return prefix, int(suffix)
    raise ValueError(f"Cannot parse entity: {entity_str}")
