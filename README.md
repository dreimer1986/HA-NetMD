# NetMD

Native Python Home Assistant integration for USB-connected NetMD players and recorders. No `netmdcli` process or bundled executable is used.

Copy this complete directory to `/config/custom_components/netmd`, restart Home Assistant, connect the NetMD device over USB, and add **NetMD** under **Settings → Devices & services**. Home Assistant OS normally exposes the USB bus to Core automatically. Container installations must pass `/dev/bus/usb` through to the Home Assistant container.

The integration provides playback, track selection, seeking, disc and track metadata, capacity sensors, and actions for renaming, moving, playing, and deleting tracks. Track numbers in action data start at 1.

Audio transfer only works via Line-In of a sound card. My examples show a USB Sound card on the very same host HA is running on and the Player is plugged into either.

## General

This setup creates a remote controllable stream on http://homeassistant.local:8888/live.mp3 that you can use as Radio station inside your Music Assistant instance or any other Player you want to use.

## Configuration.yaml

### set_minidisc_linein_port:
Only needed if your sink switches back to microphone after reboot.

### set_minidisc_linein_vol:
Only needed if your volume needs to be set back to 70% after reboot.

Both are only there for reference. I dont need them after I used both once.

#### P.S.
"alsa_input.usb-0d8c_USB_Sound_Device-00.analog-stereo" is the name of the line-in audio input sink in my case. You need to find your own line-in first. For that "pactl list | less" is your best friend. Look for the name of your own line-in device and replace it on the commands.

## SSH
If you want to be able to change the default input and volume by shell_command at all, you need to abuse ssh for tinkering from one Docker inside another:

mkdir -p /config/.ssh
cd /config/.ssh
ssh-keygen -t rsa -b 4096 -f /config/.ssh/id_rsa -N ""
chmod 700 /config/.ssh
chmod 600 /config/.ssh/id_rsa
chmod 644 /config/.ssh/id_rsa.pub

Now you can use the shell commands I made for that.
