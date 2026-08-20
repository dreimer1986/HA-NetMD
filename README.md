# HA-NetMD - Control and listen to your MiniDisc everywhere!

Native Python Home Assistant integration for USB-connected NetMD players and recorders. No `netmdcli` process or bundled executable is used.
This setup creates a remote controllable stream on http://homeassistant.local:8888/live.mp3 that you can use as Radio Station inside your Music Assistant instance or any other media player you want to use.

* [Features](#features)
  * [Actions](#actions)
    * [Rename track](#rename_track)
    * [Rename disc](#rename_disc)
    * [Move track](#move_track)
    * [Delete track](#delete_track)
    * [Play track](#play_track)
    * [Fast forward](#fast_forward)
    * [Rewind](#rewind)
* [HACS Install](#hacs_install)
* [Manual Install](#manual_install)
  * [Automations.yaml](#automations)
    * [MiniDisc Start](#minidisc_start)
    * [MiniDisc Stop](#minidisc_stop)
  * [Configuration.yaml](#configuration)
    * [shell_command](#shell_command)
      * [set_minidisc_linein_port](#set_minidisc_linein_port)
      * [set_minidisc_linein_vol](#set_minidisc_linein_vol)
    * [command_line](#command_line)
      * [FFmpeg Stream](#ffmpeg_stream)
      * [FFmpeg Status](#ffmpeg_status)
      * [MiniDisc Streamer Status](#minidisc_streamer_status)
  * [P.S.](#ps)
  * [SSH](#ssh)
* [Playback with Music Assistant](#playback_ma)
* [Pictures](#pictures)

## <a name="features"></a>Features

The integration provides playback, track selection, seeking, disc and track metadata, capacity sensors, and actions for renaming, moving, playing, and deleting tracks. Track numbers in action data start at 1.
Audio transfer only works via Line-In of a sound card as the NetMD-Protocol does not allow direct streaming of audio.

### <a name="rename_track"></a>Rename track

Rename a track on the inserted MiniDisc.

**Target:** Target NetMD Device or media_player entity.<br>
**Track Number:** Track to be renamed. Track numbers start at 1.<br>
**Title:** New Title of the Title.

### <a name="ename_disc"></a>Rename disc

Rename the inserted MiniDisc while preserving its group metadata.

**Target:** Target NetMD Device or media_player entity.<br>
**Title:** New Title of the MiniDisc.

### <a name="move_track"></a>Move track

Move a track to another position.

**Target:** Target NetMD Device or media_player entity.<br>
**Source Track Number:** Source Track number. Track numbers start at 1.<br>
**Destination Track Number:** Destination Track number. Track numbers start at 1.

### <a name="delete_track"></a>Delete track

Permanently delete a track from the inserted MiniDisc.

**Target:** Target NetMD Device or media_player entity.<br>
**Track Number:** Track to be deleted. WARNING! This cannot be made undone! Track numbers start at 1.

### <a name="play_track"></a>Play track

Select and play a track.

**Target:** Target NetMD Device or media_player entity.<br>
**Track Number:** Track to be played. Track numbers start at 1.

### <a name="fast_forward"></a>Fast forward

Start fast-forwarding the current track on the inserted MiniDisc.

**Target:** Target NetMD Device or media_player entity.

### <a name="rewind"></a>Rewind

Start rewinding the current track on the inserted MiniDisc.

**Target:** Target NetMD Device or media_player entity.

## <a name="hacs_install"></a>HACS Install

Integrate https://github.com/dreimer1986/HA-NetMD as repository for an **Integration** into HACS and install **HA-NetMD** with HACS.

## <a name="manual_install"></a>Manual Install

Copy the complete `netmd` directory to `/config/custom_components/netmd`, restart Home Assistant, connect the NetMD device over USB, and add **NetMD** under **Settings → Devices & services**.
* Home Assistant OS normally exposes the USB bus to Core automatically.
* Container installations must pass `/dev/bus/usb` through to the Home Assistant container.

### <a name="automations"></a>Automations.yaml

#### <a name="minidisc_start"></a>MiniDisc Start

This automation waits for the NetMD media_player entity to start playback or come online. If this happens it starts the FFmpeg stream.

#### <a name="minidisc_stop"></a>MiniDisc Stop

This automation waits for the NetMD media_player entity to stop playback or become offline. If this happens it stops the FFmpeg stream.

### <a name="configuration"></a>Configuration.yaml

#### <a name="shell_command"></a>shell_command

##### <a name="set_minidisc_linein_port"></a>set_minidisc_linein_port

Only needed if your pulse audio sink switches back to microphone port as default after reboot.

##### <a name="set_minidisc_linein_vol"></a>set_minidisc_linein_vol

Only needed if your line-in volume needs to be set back to 70% after reboot.

The last two are only there for reference. I don't need them anymore after I used both once.

#### <a name="command_line"></a>command_line

##### <a name="ffmpeg_stream"></a>FFmpeg Stream

This switch controls the running as background process FFmpeg with the sound card's line-in as input and the URL on port 8888 as stream in MP3 format as output. To allow more than one connection and stay alive when the stream is stopped for a short while a Python script is now creating a asynchronous web server that hosts the FFmpeg conversion via pipe.

##### <a name="ffmpeg_status"></a>FFmpeg Status

This sensor outputs the last line of the debug log the stream service creates. Thus you can follow problems showing up by checking this sensor.

##### <a name="minidisc_streamer_status"></a>MiniDisc Streamer Status

This sensor outputs if the FFmpeg process is running or not. It verifies this by checking if the PID that was logged when FFmpeg was started is still active or not.

### <a name="ps"></a>P.S.

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

## <a name="playback_ma"></a>Playback with Music Assistant

The most effective way to play the MiniDisc contents with this Addon would be Music Assistant.

1. Install the Home Assistant App from the integrated App Store and configure it to your wishes. The app has dozes of ways to connect to whatever playback options you have in your network. Of course you can use the web browser you use right now to set it up as playback option, too.

2. To have a nice logo for the Stream you first copy /homeassistant/custom_components/netmd/brand/icon.png to /homeassistant/www/icon.png. This will be needed later in the process.

3. The Addon sets up a music stream as already explained above. Thus we need a way to connect to this stream. In Music Assistant you need to look for the menu item "Radios". Then the three dots in the top right corner and in the menu there you need to click on "Add by URL".
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/ma_setup_radio.png" alt="Music Assistant Radio Stream Setup">
</p>

4. In the following window you add the settings and path the following way:
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/ma_setup_radio_2.png" alt="Music Assistant Radio Stream Setup 2">
</p>

5. Now the Radio Stream is fully setup and can be selected as source for whatever plackback option you have available. This works on the official Music Assistant App for playback, it was tested in Android Auto and CarPlay, too.
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/ma_setup_radio_3.png" alt="Music Assistant Radio Stream Setup 3">
</p>

## <a name="pictures"></a>Pictures

My Home Assistant Server based on a NUC7I7BNB, a CC2652 Dev board for Zigbee, a USB Sound Card and a Sonoff Zigbee USB Dongle for Matter/Thread
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/Host.jpg" alt="Host Hardware">
</p>

The Add-On running inside Home Assistant.
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/HA.png" alt="Home Assistant Entities">
</p>

Pics from usage on my Pixel 7 Pro:

Listening to the Add-On's stream inside Music Assistant.
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/mobile.png" alt="Playback in Music Assistant">
</p>

Splitscreen: Controlling the current track being played back via Home Assistant app (below) and listening to the Add-On's stream inside Music Assistant (above)
<p align="center">
  <img src="https://raw.githubusercontent.com/dreimer1986/HA-NetMD/refs/heads/master/media/mobile-split.png" alt="Splitscreen controlling and listening">
</p>
