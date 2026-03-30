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
DEFAULT_SCAN_INTERVAL = 1  # seconds

# VM address maps per LOGO! model
# Each block: start byte in VM, max count, type (digital=bit, analog=word)
VM_MAPS = {
    "0BA8": {
        "I":   {"start": 1024, "count": 24, "type": "digital"},
        "Q":   {"start": 1064, "count": 20, "type": "digital"},
        "M":   {"start": 1104, "count": 64, "type": "digital"},
        "NI":  {"start": 1246, "count": 64, "type": "digital"},
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
# NI -> switch (writable digital)
# I, Q, M, NQ -> binary_sensor (read-only digital)
# NAI -> number (writable analog)
# AI, AQ, NAQ -> sensor (read-only analog)
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

PLATFORMS = ["switch", "binary_sensor", "sensor", "number"]


def resolve_address(model: str, block_name: str, block_number: int):
    """Resolve a block reference (e.g. NI1) to a VM byte offset and bit offset.

    Returns (byte_offset, bit_offset) for digital blocks.
    Returns (byte_offset, None) for analog blocks.
    Raises ValueError if block_name or block_number is invalid.
    """
    vm_map = VM_MAPS.get(model)
    if vm_map is None:
        raise ValueError(f"Unknown LOGO! model: {model}")

    block = vm_map.get(block_name)
    if block is None:
        raise ValueError(f"Unknown block: {block_name}")

    if block_number < 1 or block_number > block["count"]:
        raise ValueError(
            f"{block_name}{block_number} out of range "
            f"(max {block_name}{block['count']})"
        )

    if block["type"] == "digital":
        byte_offset = block["start"] + (block_number - 1) // 8
        bit_offset = (block_number - 1) % 8
        return byte_offset, bit_offset
    else:
        byte_offset = block["start"] + (block_number - 1) * 2
        return byte_offset, None


def get_vm_read_ranges(model: str):
    """Get the VM byte ranges to read for a model.

    Returns a list of (start, size) tuples. Split into chunks that fit
    within the LOGO! PDU size limit (~240 bytes per read).
    """
    vm_map = VM_MAPS.get(model)
    if vm_map is None:
        raise ValueError(f"Unknown LOGO! model: {model}")

    all_starts = []
    all_ends = []
    for block in vm_map.values():
        start = block["start"]
        if block["type"] == "digital":
            end = start + (block["count"] + 7) // 8
        else:
            end = start + block["count"] * 2
        all_starts.append(start)
        all_ends.append(end)

    vm_start = min(all_starts)
    vm_end = max(all_ends)
    total = vm_end - vm_start

    # Split into chunks of max 200 bytes to stay within PDU limits
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
    """Parse a block reference string like 'NI1' into (block_name, block_number).

    Handles: I1, Q1, M1, NI1, NQ1, AI1, AQ1, NAI1, NAQ1
    """
    entity_str = entity_str.strip().upper()
    # Try two-letter prefix first, then three-letter
    for prefix_len in (3, 2, 1):
        prefix = entity_str[:prefix_len]
        suffix = entity_str[prefix_len:]
        if prefix in PLATFORM_MAP and suffix.isdigit():
            return prefix, int(suffix)
    raise ValueError(f"Cannot parse entity: {entity_str}")
