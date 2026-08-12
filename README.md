# HA-NetMD - Control and listen to your MiniDisc everywhere!

Native Python Home Assistant integration for USB-connected NetMD players and recorders. No `netmdcli` process or bundled executable is used.
This setup creates a remote controllable stream on http://homeassistant.local:8888/live.mp3 that you can use as Radio Station inside your Music Assistant instance or any other media player you want to use.

* [Features](#features)
* [HACS Install](#hacs_install)
* [Manual Install](#manual_install)
  * [Automations.yaml](#automations)
    * [MiniDisc Start](#minidisc_start)
    * [MiniDisc Stop](#minidisc_stop)
  * [Configuration.yaml](#configuration)
    * [start_ffmpeg_minidisc](#start_ffmpeg_minidisc)
    * [stop_ffmpeg_minidisc](#stop_ffmpeg_minidisc)
    * [set_minidisc_linein_port](#set_minidisc_linein_port)
    * [set_minidisc_linein_vol](#set_minidisc_linein_vol)
  * [P.S.](#ps)
  * [SSH](#ssh)
* [Pictures](#pictures)

## <a name="features"></a>Features

The integration provides playback, track selection, seeking, disc and track metadata, capacity sensors, and actions for renaming, moving, playing, and deleting tracks. Track numbers in action data start at 1.
Audio transfer only works via Line-In of a sound card as the NetMD-Protocol does not allow direct streaming of audio.

## <a name="hacs_install"></a>HACS Install

Integrate https://github.com/dreimer1986/HA-NetMD as repository for an **Integration** into HACS and install **HA-NetMD** with HACS.

## <a name="manual_install"></a>Manual Install

Copy the complete `netmd` directory to `/config/custom_components/netmd`, restart Home Assistant, connect the NetMD device over USB, and add **NetMD** under **Settings → Devices & services**.
* Home Assistant OS normally exposes the USB bus to Core automatically.
* Container installations must pass `/dev/bus/usb` through to the Home Assistant container.

### <a name="automations"></a>Automations.yaml

#### <a name="minidisc_start"></a>MiniDisc Start

This automation waits for the NetMD media_player entity to start playback or come online. If this happens it starts the FFMPEG stream.

#### <a name="minidisc_stop"></a>MiniDisc Stop

This automation waits for the NetMD media_player entity to stop playback or become offline. If this happens it stops the FFMPEG stream.

### <a name="configuration"></a>Configuration.yaml

#### <a name="start_ffmpeg_minidisc"></a>start_ffmpeg_minidisc

This command opens FFMPEG with the sound card's line-in as input and the URL on port 8888 as stream in MP3 format.

#### <a name="stop_ffmpeg_minidisc"></a>stop_ffmpeg_minidisc

This command closes exactly the FFMPEG session we opened before and keeps the rest alone.

#### <a name="set_minidisc_linein_port"></a>set_minidisc_linein_port

Only needed if your pulse audio sink switches back to microphone port as default after reboot.

#### <a name="set_minidisc_linein_vol"></a>set_minidisc_linein_vol

Only needed if your line-in volume needs to be set back to 70% after reboot.

The last two are only there for reference. I don't need them anymore after I used both once.

#### <a name="ps"></a>P.S.

"alsa_input.usb-0d8c_USB_Sound_Device-00.analog-stereo" is the name of the line-in audio input sink in my case. You need to find your own line-in first. For that "pactl list | less" is your best friend. Look for the name of your own line-in device and replace it on the commands.

### <a name="ssh"></a>SSH

If you want to be able to change the default input and volume by shell_command at all, you need to abuse SSH for tinkering from one Docker inside another:

```
mkdir -p /config/.ssh
cd /config/.ssh
ssh-keygen -t rsa -b 4096 -f /config/.ssh/id_rsa -N ""
chmod 700 /config/.ssh
chmod 600 /config/.ssh/id_rsa
chmod 644 /config/.ssh/id_rsa.pub
```

Now you can use the shell commands I made for that.

## <a name="pictures"></a>Pictures

My Home Assistant Server based on a NUC7I7BNB, a CC2652 Dev board for Zigbee, a USB Sound Card and a Sonoff Zigbee USB Dongle for Matter/Thread
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/Host.jpg" alt="Host Hardware">
</p>

The Add-On running inside Home Assistant.
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/HA.png" alt="Home Assistant Entities">
</p>
