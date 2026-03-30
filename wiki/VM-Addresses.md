# VM Addresses

All I/O is accessed through the VM (Variable Memory) area, exposed as DB1 via the S7 protocol.

## LOGO! 0BA7

| Block | VM Start | Count | Type |
|-------|----------|-------|------|
| I | `923` (V923.0) | 24 | Digital (bit) |
| Q | `942` (V942.0) | 16 | Digital (bit) |
| M | `948` (V948.0) | 27 | Digital (bit) |
| AI | `926` (VW926) | 8 | Analog (16-bit word) |
| AQ | `944` (VW944) | 2 | Analog (16-bit word) |
| AM | `952` (VW952) | 16 | Analog (16-bit word) |

## LOGO! 0BA8 and 0BA9

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

> **NI/NQ/NAI/NAQ addresses** are determined by the **Parameter VM Mapping** configured in LOGO! Soft Comfort. The defaults above assume the standard mapping starting at V0.0. If you have customised this in your project, use the per-entity address override during setup.

## Address formats

**Digital:** `byte.bit` — e.g. `0.0` for V0.0, `0.7` for V0.7, `1.0` for V1.0

**Analog:** byte offset only — e.g. `1032` for VW1032

You can override the default address for any entity during setup or via the options flow (see [Setup & Options](Setup-and-Options)).

When configuring manually via the storage file, use the formulas in [Manual Configuration](Manual-Configuration) to compute the correct offsets.
