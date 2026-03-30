# Service Actions

The integration exposes two service actions available under **Developer Tools → Actions** or in automations/scripts.

## `siemens_logo.write_block`

Write a value directly to any LOGO! block address — useful for blocks not set up as entities.

| Field | Required | Description |
|-------|----------|-------------|
| `config_entry_id` | Yes | Which LOGO! device to target |
| `block` | Yes | Block address, e.g. `NI1`, `NAI2` |
| `value` | Yes | `true`/`false` for digital (NI), integer for analog (NAI) |

**Example — turn on NI1:**
```yaml
action: siemens_logo.write_block
data:
  config_entry_id: "abc123"
  block: "NI1"
  value: true
```

**Example — set NAI1 to 750:**
```yaml
action: siemens_logo.write_block
data:
  config_entry_id: "abc123"
  block: "NAI1"
  value: 750
```

## `siemens_logo.read_block`

Read the live value of any block directly from the PLC. Returns a response dict with a `value` key.

| Field | Required | Description |
|-------|----------|-------------|
| `config_entry_id` | Yes | Which LOGO! device to target |
| `block` | Yes | Block address, e.g. `AI1`, `Q2`, `I3` |

**Example — read AI1 in an automation:**
```yaml
action: siemens_logo.read_block
data:
  config_entry_id: "abc123"
  block: "AI1"
response_variable: result
# result.value contains the integer reading
```

## Finding your config_entry_id

Go to **Settings → Devices & Services → Siemens LOGO!** → three-dot menu → **System information**. The entry ID is shown there.

Alternatively use **Developer Tools → Template**:
```
{{ integration_entities('siemens_logo') }}
```
