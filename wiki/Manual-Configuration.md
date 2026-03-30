# Manual Configuration

This integration is config-entry based and is normally set up through the UI. There is no `configuration.yaml` support. However, you can create or edit a config entry directly by editing the Home Assistant storage file — useful for scripted deployments, migrating between systems, or bulk-editing many entities without clicking through the UI.

> **Warning:** editing storage files directly can corrupt your HA configuration if the JSON is malformed. Always make a backup first.

## Storage file location

```
config/.storage/core.config_entries
```

## Entry structure

Each LOGO! integration instance is one entry in the `data.entries` array. A complete entry looks like this:

```json
{
  "entry_id": "your_unique_entry_id",
  "version": 1,
  "minor_version": 1,
  "domain": "siemens_logo",
  "title": "LOGO! 192.168.1.50",
  "data": {
    "host": "192.168.1.50",
    "rack": 0,
    "slot": 1,
    "model": "0BA8",
    "scan_interval": 1000,
    "entities": [
      {
        "block": "NI",
        "number": 1,
        "platform": "switch",
        "name": "Pump",
        "unique_id": null,
        "byte_offset": 0,
        "bit_offset": 0
      },
      {
        "block": "NI",
        "number": 2,
        "platform": "button",
        "name": "Reset",
        "unique_id": null,
        "byte_offset": 0,
        "bit_offset": 1
      },
      {
        "block": "Q",
        "number": 1,
        "platform": "binary_sensor",
        "name": "Motor running",
        "unique_id": null,
        "byte_offset": 1064,
        "bit_offset": 0
      },
      {
        "block": "AI",
        "number": 1,
        "platform": "sensor",
        "name": "Tank level",
        "unique_id": null,
        "byte_offset": 1032,
        "bit_offset": null
      },
      {
        "block": "NAI",
        "number": 1,
        "platform": "number",
        "name": "Setpoint",
        "unique_id": null,
        "byte_offset": 1262,
        "bit_offset": null
      }
    ]
  },
  "options": {},
  "source": "user",
  "unique_id": "192.168.1.50",
  "disabled_by": null
}
```

## Field reference

### Connection fields

| Field | Type | Description |
|-------|------|-------------|
| `host` | string | IP address of the LOGO! |
| `rack` | int | S7 rack number, typically `0` |
| `slot` | int | S7 slot number, typically `1` |
| `model` | string | `"0BA7"`, `"0BA8"`, or `"0BA9"` |
| `scan_interval` | int | Poll interval in milliseconds (min 100) |

### Entity fields

| Field | Type | Description |
|-------|------|-------------|
| `block` | string | Block type: `I`, `Q`, `M`, `NI`, `NQ`, `AI`, `AQ`, `AM`, `NAI`, `NAQ` |
| `number` | int | Block number (1-based) |
| `platform` | string | HA platform — see table below |
| `name` | string | Friendly name shown in HA |
| `unique_id` | string or null | Custom unique ID, or `null` to auto-generate |
| `byte_offset` | int | VM byte offset (see [VM Addresses](VM-Addresses)) |
| `bit_offset` | int or null | Bit position within byte for digital blocks, `null` for analog |

### Platform values

| Block | Normal platform | Push button platform |
|-------|----------------|----------------------|
| `I`, `Q`, `M`, `NQ` | `"binary_sensor"` | — |
| `NI` | `"switch"` | `"button"` |
| `AI`, `AQ`, `AM`, `NAQ` | `"sensor"` | — |
| `NAI` | `"number"` | — |

## Computing VM addresses

Use the tables in [VM Addresses](VM-Addresses) to compute `byte_offset` and `bit_offset` for each entity.

**Digital blocks** (I, Q, M, NI, NQ):
```
byte_offset = block_start + (number - 1) // 8
bit_offset  = (number - 1) % 8
```

Example — NI3 on 0BA8 (block start = 0):
```
byte_offset = 0 + (3 - 1) // 8 = 0
bit_offset  = (3 - 1) % 8      = 2
```

**Analog blocks** (AI, AQ, AM, NAI, NAQ):
```
byte_offset = block_start + (number - 1) * 2
bit_offset  = null
```

Example — AI2 on 0BA8 (block start = 1032):
```
byte_offset = 1032 + (2 - 1) * 2 = 1034
bit_offset  = null
```

## Applying the changes

After editing the file:

1. Verify the JSON is valid (e.g. paste it into [jsonlint.com](https://jsonlint.com))
2. Restart Home Assistant

The integration will load the entry on startup and create all entities automatically.
