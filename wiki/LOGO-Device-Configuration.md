# LOGO! Device Configuration

Before adding the integration, you must enable external read/write access on the PLC.

## Enabling PUT/GET access

1. Open **LOGO! Soft Comfort**
2. Go to **Tools → Ethernet Connections** (or **Network settings** depending on your version)
3. Enable **"Allow PUT/GET communication from remote partner"**
4. Transfer the updated configuration to the device

Without PUT/GET enabled the integration will be unable to read or write the VM (Variable Memory) area and the connection will fail.

## Verifying connectivity

Check that the PLC is reachable from the Home Assistant host before adding the integration:

```
ping <logo-ip-address>
```

For LOGO! 0BA8 the default rack is `0` and slot is `1`.
