# Push Button Mode

NI entities can be configured as **push buttons** instead of switches. When pressed in Home Assistant, the integration:

1. Sets the bit to `True`
2. Waits 500 ms
3. Sets the bit back to `False`

This is useful for triggering momentary actions in the LOGO! program (e.g. simulating a physical button press without having to manually turn it off again).

## Enabling push button mode

During setup (or when editing via the options flow), the address step shows a **"Push button"** toggle for each NI entity. Enable it to use button mode instead of switch mode.

The entity will appear as a **Button** in Home Assistant rather than a Switch.
