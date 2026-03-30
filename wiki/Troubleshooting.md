# Troubleshooting

## Integration fails to connect

- Verify the IP address and that the PLC is reachable: `ping <ip>`
- Confirm PUT/GET is enabled in LOGO! Soft Comfort (see [LOGO! Device Configuration](LOGO-Device-Configuration))
- Check that rack=`0` and slot=`1` (correct for LOGO! 0BA8/0BA9)

## Switches turn on in Home Assistant but nothing happens on the PLC

- Open LOGO! Soft Comfort in online mode and check the live value of the NI block
- Verify the VM address matches what your LOGO! program uses (NI1 = V0.0 by default)
- Enable debug logging to inspect the raw bytes being written:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.siemens_logo: debug
```

## Poll interval warning / integration stops updating

- Increase the poll interval — try 500 ms or 1000 ms
- Each poll opens a DB1 read over TCP; too-frequent reads can saturate the LOGO!'s small network stack

## Entities show unavailable after HA restart

- The integration will retry the connection automatically. If it keeps failing, check network connectivity and that the PLC is powered on.
- Check the HA logs (**Settings → System → Logs**) for `ConfigEntryNotReady` messages.
