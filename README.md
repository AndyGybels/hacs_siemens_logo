# Siemens LOGO! Integration for Home Assistant

A custom Home Assistant integration for the **Siemens LOGO! 0BA8** PLC, providing real-time monitoring and control of inputs, outputs, markers, and analog channels via the S7 protocol.

---

## Features

- **Polling-based** local connection — no cloud dependency
- Configurable poll interval (minimum 100 ms)
- Supports **LOGO! 0BA7, 0BA8, and 0BA9 (8.3)** hardware generations
- Supports all major block types:

| Block | Description | Platform | Direction | Models |
|-------|-------------|----------|-----------|--------|
| `I` | Digital input | Binary Sensor | Read | All |
| `Q` | Digital output | Binary Sensor | Read | All |
| `M` | Marker / flag | Binary Sensor | Read | All |
| `AI` | Analog input | Sensor | Read | All |
| `AQ` | Analog output | Sensor | Read | All |
| `AM` | Analog marker | Sensor | Read | All |
| `NI` | Network input (digital) | Switch or Button | Read / Write | 0BA8, 0BA9 |
| `NQ` | Network output (digital) | Binary Sensor | Read | 0BA8, 0BA9 |
| `NAI` | Network analog input | Number | Read / Write | 0BA8, 0BA9 |
| `NAQ` | Network analog output | Sensor | Read | 0BA8, 0BA9 |

- **Per-entity VM address override** — map any entity to a custom memory address instead of the default
- **Push button mode** for NI entities — sends a momentary pulse (configurable duration) instead of a latching on/off
- **Friendly name and unique ID** configurable per entity in the UI
- Full UI configuration: setup, options, and reconfigure flows

---

## Supported Hardware

| Model | Generation | Ethernet | Network vars (NI/NQ/NAI/NAQ) |
|-------|-----------|----------|-------------------------------|
| LOGO! 0BA7 | 7th gen | Built-in (some variants) or expansion module | No |
| LOGO! 0BA8 | 8th gen (8.0 / 8.2) | Built-in | Yes |
| LOGO! 0BA9 | 8.3 | Built-in | Yes |

> Older generations (0BA4–0BA6) do not support the S7 protocol and are not compatible.

---

## Requirements

- Home Assistant 2024.1 or later
- Siemens LOGO! 0BA7, 0BA8, or 0BA9
- **PUT/GET access must be enabled** on the LOGO! device (see [LOGO! configuration](#logo-configuration))
- Network connectivity between Home Assistant and the PLC

---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **Siemens LOGO!** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/siemens_logo` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

---

## LOGO! Configuration

Before adding the integration, you must enable external read/write access on the PLC:

1. Open **LOGO! Soft Comfort**
2. Go to **Tools → Ethernet Connections** (or **Network settings** depending on version)
3. Enable **"Allow PUT/GET communication from remote partner"**
4. Transfer the updated configuration to the device

> Without PUT/GET enabled, the integration will be unable to read or write the VM (Variable Memory) area.

---

## Setup

### Adding the integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Siemens LOGO!**
3. Fill in the connection settings:

| Field | Description | Default |
|-------|-------------|---------|
| IP Address | IP address of the LOGO! on your network | — |
| Rack | S7 rack number | `0` |
| Slot | S7 slot number | `1` |
| LOGO! Model | Hardware generation (`0BA7`, `0BA8`, `0BA9`) | `0BA8` |
| Poll Interval (ms) | How often to read the PLC state | `1000` |

> Setting the poll interval too low (below ~200 ms in practice) can overload the connection and cause the integration to stop responding.

4. Enter the entities you want to expose, as a comma-separated list of block addresses. Examples:

```
NI1, NI2, NI3, Q1, Q2, AI1, AI2, NAI1
```

5. For each entity, confirm or override the **VM address**, set a **friendly name**, optionally provide a **unique ID**, and for NI entities choose whether to make it a **push button**.

---

## VM Addresses

All I/O is accessed through the VM (Variable Memory) area, exposed as DB1 via the S7 protocol. Default address mappings per model:

### LOGO! 0BA7

| Block | VM Start | Count | Type |
|-------|----------|-------|------|
| I | `923` (V923.0) | 24 | Digital (bit) |
| Q | `942` (V942.0) | 16 | Digital (bit) |
| M | `948` (V948.0) | 27 | Digital (bit) |
| AI | `926` (VW926) | 8 | Analog (16-bit word) |
| AQ | `944` (VW944) | 2 | Analog (16-bit word) |
| AM | `952` (VW952) | 16 | Analog (16-bit word) |

### LOGO! 0BA8 and 0BA9

| Block | VM Start | Count | Type |
|-------|----------|-------|------|
| I | `1024` (V1024.0) | 24 | Digital (bit) |
| Q | `1064` (V1064.0) | 20 | Digital (bit) |
| M | `1104` (V1104.0) | 64 | Digital (bit) |
| NI | `0` (V0.0) | 64 | Digital (bit) |
| NQ | `1254` (V1254.0) | 64 | Digital (bit) |
| AI | `1032` (VW1032) | 8 | Analog (16-bit word) |
| AQ | `1072` (VW1072) | 8 | Analog (16-bit word) |
| AM | `1118` (VW1118) | 64 | Analog (16-bit word) |
| NAI | `1262` (VW1262) | 32 | Analog (16-bit word) |
| NAQ | `1326` (VW1326) | 16 | Analog (16-bit word) |

> **NI/NQ/NAI/NAQ addresses** for 0BA8/0BA9 are determined by the **Parameter VM Mapping** configured in LOGO! Soft Comfort. The defaults above assume the standard mapping starting at V0.0. If you have customised this in your project, use the per-entity address override during setup to match.

**Digital address format:** `byte.bit` — e.g. `0.0` for V0.0, `0.7` for V0.7, `1.0` for V1.0

**Analog address format:** byte offset only — e.g. `1032` for VW1032

You can override the default address for any entity during setup, which is useful if your LOGO! program uses a non-standard memory layout.

---

## Push Button Mode

NI entities can be configured as **push buttons** instead of switches. When pressed in Home Assistant, the integration:

1. Sets the bit to `True`
2. Waits 500 ms
3. Sets the bit back to `False`

This is useful for triggering momentary actions in the LOGO! program (e.g. simulating a physical button press).

---

## Removing the integration

1. Go to **Settings → Devices & Services**
2. Find the **Siemens LOGO!** integration card
3. Click the three-dot menu → **Delete**
4. Confirm the removal

All entities, devices, and automations referencing them will be removed. The LOGO! device itself is not affected — it continues running its program.

---

## Reconfiguring

- **Reconfigure** (gear icon on the integration card): change the IP address, rack, slot, model, or poll interval for an existing entry
- **Configure** (three-dot menu → Configure): edit the entity list, addresses, names, and push button settings without removing and re-adding the integration

---

## Development

### Project structure

```
hacs_siemens_logo/
├── custom_components/siemens_logo/
│   ├── __init__.py          # LogoConnection, async_setup_entry, async_unload_entry
│   ├── config_flow.py       # UI setup/options/reconfigure flows
│   ├── const.py             # Constants, VM maps, address utilities
│   ├── coordinator.py       # DataUpdateCoordinator (polling)
│   ├── binary_sensor.py
│   ├── button.py
│   ├── number.py
│   ├── sensor.py
│   ├── switch.py
│   ├── manifest.json
│   └── strings.json
├── tests/
│   ├── conftest.py
│   ├── test_const.py
│   ├── test_config_flow.py
│   ├── test_init.py
│   ├── test_switch.py
│   └── test_button.py
├── .github/workflows/tests.yml
├── pytest.ini
├── requirements_test.txt
└── README.md
```

### Running the tests

```bash
pip install -r requirements_test.txt
pytest tests/ -v
```

The test suite does **not** require a physical PLC or the native `snap7` library — both are stubbed out in `conftest.py`.

---

## Troubleshooting

**Integration fails to connect**
- Verify the IP address and that the PLC is reachable (`ping <ip>`)
- Confirm PUT/GET is enabled in LOGO! Soft Comfort
- Check that rack=0 and slot=1 (correct for LOGO! 0BA8)

**Switches turn on in Home Assistant but nothing happens on the PLC**
- Open LOGO! Soft Comfort in online mode and check the live value of the NI block
- Verify the VM address matches what your LOGO! program uses (NI1 = V0.0 by default)
- Enable debug logging to inspect the raw bytes being written:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.siemens_logo: debug
```

**Poll interval warning / integration stops updating**
- Increase the poll interval — try 500 ms or 1000 ms
- Each poll opens a DB1 read over TCP; too-frequent reads can saturate the LOGO!'s small network stack
