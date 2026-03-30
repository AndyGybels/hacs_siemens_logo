# Installation

## Requirements

- Home Assistant 2024.1 or later
- Siemens LOGO! 0BA7, 0BA8, or 0BA9
- Network connectivity between Home Assistant and the PLC
- PUT/GET access enabled on the LOGO! (see [LOGO! Device Configuration](LOGO-Device-Configuration))

## HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **Siemens LOGO!** and install it
5. Restart Home Assistant

## Manual

1. Copy the `custom_components/siemens_logo` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

After installing, follow [Setup & Options](Setup-and-Options) to add the integration via the UI, or [Manual Configuration](Manual-Configuration) for a storage-file approach.

## Removing the integration

1. Go to **Settings → Devices & Services**
2. Find the **Siemens LOGO!** integration card
3. Click the three-dot menu → **Delete**
4. Confirm the removal

All entities, devices, and automations referencing them will be removed. The LOGO! device itself is not affected — it continues running its program.
