# NetMD

Native Python Home Assistant integration for USB-connected NetMD players and
recorders. No `netmdcli` process or bundled executable is used.

Copy this complete directory to `/config/custom_components/netmd`, restart Home
Assistant, connect the NetMD device over USB, and add **NetMD** under
**Settings → Devices & services**. Home Assistant OS normally exposes the USB
bus to Core automatically. Container installations must pass `/dev/bus/usb`
through to the Home Assistant container.

The integration provides playback, track selection, seeking, disc and track
metadata, capacity sensors, and actions for renaming, moving, playing, and
deleting tracks. Track numbers in action data start at 1.

High-speed audio transfer is deliberately not part of version 0.1.0. It uses a
separate secure-transfer protocol with device-specific behavior and needs real
hardware acceptance tests before it can safely be exposed through Home
Assistant.

