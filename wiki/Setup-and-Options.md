# Setup & Options

> You can also configure the integration via `configuration.yaml` instead of the UI — see [Manual Configuration](Manual-Configuration).

## Adding the integration

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

4. Enter the entities you want to expose as a comma-separated list of block addresses:

```
NI1, NI2, NI3, Q1, Q2, AI1, AI2, NAI1
```

Supported block types:

| Block | Description | Platform | Writable |
|-------|-------------|----------|----------|
| `I` | Digital input | Binary Sensor | No |
| `Q` | Digital output | Binary Sensor | No |
| `M` | Marker / flag | Binary Sensor | No |
| `AI` | Analog input | Sensor | No |
| `AQ` | Analog output | Sensor | No |
| `AM` | Analog marker | Sensor | No |
| `NI` | Network input | Switch or Button | Yes |
| `NQ` | Network output | Binary Sensor | No |
| `NAI` | Network analog input | Number | Yes |
| `NAQ` | Network analog output | Sensor | No |

5. For each entity, confirm or override the **VM address**, set a **friendly name**, optionally provide a **unique ID**, and for NI entities choose whether to make it a **push button** (see [Push Button Mode](Push-Button-Mode)).

Default VM addresses are derived automatically from the model — see [VM Addresses](VM-Addresses) for the full mapping.

## Reconfiguring

- **Reconfigure** (gear icon on the integration card): change the IP address, rack, slot, model, or poll interval
- **Configure** (three-dot menu → Configure): edit the entity list, addresses, names, and push button settings without removing and re-adding the integration

Existing entity names and addresses are pre-filled when you open the options flow.

> For scripted deployments or bulk entity edits, you can also configure the integration by editing the storage file directly — see [Manual Configuration](Manual-Configuration).

## Backing up and restoring

Your LOGO! configuration is stored in Home Assistant's config entry system. It is included in a standard HA backup (`.tar` via **Settings → System → Backups**). Restore it on another system by importing the backup — the integration and all its entities will be restored automatically.
