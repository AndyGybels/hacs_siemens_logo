# Siemens LOGO! Integration for Home Assistant

A custom Home Assistant integration for the **Siemens LOGO! 0BA7, 0BA8 and 0BA9** PLC. Provides real-time monitoring and control of inputs, outputs, markers and analog channels via the S7 protocol — no cloud, fully local.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Quick start

1. Install via HACS (add this repo as a custom repository) or copy `custom_components/siemens_logo` into your HA `config/custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **Siemens LOGO!**

> PUT/GET access must be enabled on the LOGO! device before the integration can connect. See the [wiki](../../wiki) for details.

## Documentation

All detailed documentation is in the [wiki](../../wiki):

- [Installation](../../wiki/Installation)
- [LOGO! Device Configuration](../../wiki/LOGO-Device-Configuration)
- [Setup & Options](../../wiki/Setup-and-Options)
- [VM Addresses](../../wiki/VM-Addresses)
- [Push Button Mode](../../wiki/Push-Button-Mode)
- [Service Actions](../../wiki/Service-Actions)
- [Troubleshooting](../../wiki/Troubleshooting)
- [Development](../../wiki/Development)

## Supported hardware

| Model | Generation | Network vars (NI/NQ/NAI/NAQ) |
|-------|-----------|-------------------------------|
| LOGO! 0BA7 | 7th gen | No |
| LOGO! 0BA8 | 8th gen (8.0 / 8.2) | Yes |
| LOGO! 0BA9 | 8.3 | Yes |
