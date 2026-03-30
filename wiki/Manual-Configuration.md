# Manual Configuration

You can configure the integration without the UI in two ways:

- **`configuration.yaml`** — declare devices and entities in YAML; HA imports them automatically on startup
- **Storage file editing** — edit the config entry JSON directly; useful for bulk changes to an existing entry

---

## configuration.yaml

Add a `siemens_logo` block to your `configuration.yaml`. Multiple devices are supported as a list.

```yaml
siemens_logo:
  - host: 192.168.1.50
    model: 0BA8          # 0BA7, 0BA8, or 0BA9
    rack: 0              # optional, default 0
    slot: 1              # optional, default 1
    scan_interval: 1000  # optional, milliseconds, default 1000
    entities:
      - block: NI1
        name: Pump
      - block: NI2
        name: Reset button
        push_button: true
      - block: Q1
        name: Motor running
      - block: AI1
        name: Tank level
      - block: NAI1
        name: Setpoint
        address: "1262"    # optional VM address override
        unique_id: logo_setpoint_1  # optional
```

After adding or changing the YAML, restart Home Assistant. The integration creates a config entry automatically — the device will then appear under **Settings → Devices & Services** just like a UI-configured entry.

> If the host is already configured (e.g. from a previous UI setup), the import is silently skipped to avoid duplicates.

### Entity fields

| Field | Required | Description |
|-------|----------|-------------|
| `block` | Yes | Block reference, e.g. `NI1`, `Q3`, `AI2` |
| `name` | No | Friendly name shown in HA. Defaults to `LOGO NI1` etc. |
| `push_button` | No | `true` to use button mode for NI entities (default `false`) |
| `address` | No | VM address override — `byte.bit` for digital, `byte` for analog. Overrides the default for this entity. |
| `unique_id` | No | Custom unique ID. Leave out to auto-generate. |

### Supported block types

| Block | Platform | Models |
|-------|----------|--------|
| `I` | Binary Sensor | All |
| `Q` | Binary Sensor | All |
| `M` | Binary Sensor | All |
| `AI`, `AQ`, `AM` | Sensor | All |
| `NI` | Switch or Button | 0BA8, 0BA9 |
| `NQ` | Binary Sensor | 0BA8, 0BA9 |
| `NAI` | Number | 0BA8, 0BA9 |
| `NAQ` | Sensor | 0BA8, 0BA9 |

---

## Storage file editing

For bulk-editing an existing config entry without going through the UI, you can edit the storage file directly.

> **Warning:** always make a backup before editing storage files — malformed JSON will prevent HA from starting.

### File location

```
config/.storage/core.config_entries
```

### Entry structure

Each LOGO! device is one entry in the `data.entries` array:

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

### Entity field reference

| Field | Type | Description |
|-------|------|-------------|
| `block` | string | Block type: `I`, `Q`, `M`, `NI`, `NQ`, `AI`, `AQ`, `AM`, `NAI`, `NAQ` |
| `number` | int | Block number (1-based) |
| `platform` | string | `binary_sensor`, `sensor`, `switch`, `button`, or `number` |
| `name` | string | Friendly name |
| `unique_id` | string or null | Custom unique ID, or `null` to auto-generate |
| `byte_offset` | int | VM byte offset |
| `bit_offset` | int or null | Bit within byte for digital, `null` for analog |

### Computing VM addresses

See [VM Addresses](VM-Addresses) for the start offsets per block and model.

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

### Applying changes

1. Verify the JSON is valid (e.g. paste it into [jsonlint.com](https://jsonlint.com))
2. Restart Home Assistant
