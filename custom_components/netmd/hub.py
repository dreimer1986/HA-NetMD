"""Thread-safe native NetMD device hub."""

from __future__ import annotations

import threading
import time
from contextlib import suppress

import usb1

from .models import NetMDDeviceInfo, NetMDSnapshot, NetMDTrack
from .protocol import (
    CHANNELS,
    DISC_FLAG_WRITABLE,
    DISC_FLAG_WRITE_PROTECTED,
    ENCODINGS,
    OPERATING_STATUS_FAST_FORWARDING,
    OPERATING_STATUS_PAUSED,
    OPERATING_STATUS_PLAYING,
    OPERATING_STATUS_REWINDING,
    TRACK_FLAG_PROTECTED,
    NetMDError,
    NetMDProtocol,
    NetMDTransport,
    duration_to_seconds,
)


class NetMDHub:
    """Own the USB connection and serialize access to one NetMD player."""

    def __init__(self, device_info: NetMDDeviceInfo) -> None:
        self.device_info = device_info
        self._transport = NetMDTransport(device_info)
        self._protocol = NetMDProtocol(self._transport)
        self._lock = threading.Lock()
        self._connected = False
        self._metadata_dirty = True
        self._metadata_signature: tuple[str, int] | None = None
        self._last_signature_check = 0.0
        self._last_full_refresh = 0.0
        self._disc_title = ""
        self._disc_flags = 0
        self._recorded_seconds: float | None = None
        self._total_seconds: float | None = None
        self._available_seconds: float | None = None
        self._tracks: tuple[NetMDTrack, ...] = ()

    def _ensure_connected(self) -> None:
        if not self._connected:
            self._transport.open()
            self._connected = True

    def _disconnect(self) -> None:
        self._connected = False
        self._transport.close()

    def close(self) -> None:
        """Close the USB connection."""
        with self._lock:
            self._disconnect()

    def _run(self, operation, *args):
        with self._lock:
            try:
                self._ensure_connected()
                return operation(*args)
            except (usb1.USBError, NetMDError):
                self._disconnect()
                raise

    def update(self) -> NetMDSnapshot:
        """Fetch player, disc, and track state in one serialized operation."""
        return self._run(self._update)

    def _update(self) -> NetMDSnapshot:
        protocol = self._protocol
        if not protocol.is_disc_present():
            self._metadata_dirty = True
            self._metadata_signature = None
            self._tracks = ()
            return NetMDSnapshot(connected=True, disc_present=False)

        operating_status = protocol.get_operating_status()
        if operating_status == OPERATING_STATUS_PLAYING:
            playback_state = "playing"
        elif operating_status == OPERATING_STATUS_PAUSED:
            playback_state = "paused"
        elif operating_status in {
            OPERATING_STATUS_FAST_FORWARDING,
            OPERATING_STATUS_REWINDING,
        }:
            playback_state = "playing"
        else:
            playback_state = "stopped"

        position = protocol.get_position()
        current_track = position[0] if position else None
        position_seconds = None
        if position:
            position_seconds = (
                position[1] * 3600 + position[2] * 60 + position[3] + position[4] / 100
            )

        now = time.monotonic()
        check_signature = (
            self._metadata_dirty
            or self._metadata_signature is None
            or now - self._last_signature_check >= 60
            or (current_track is not None and current_track >= len(self._tracks))
        )
        if check_signature:
            raw_title = protocol.get_raw_disc_title()
            track_count = protocol.get_track_count()
            signature = (raw_title, track_count)
            self._last_signature_check = now
            full_refresh = (
                self._metadata_dirty
                or signature != self._metadata_signature
                or now - self._last_full_refresh >= 300
            )
            if full_refresh:
                groups = protocol.get_groups(track_count, raw_title)
                tracks: list[NetMDTrack] = []
                for track_index in range(track_count):
                    encoding, channel_code = protocol.get_track_encoding(track_index)
                    track_flags = protocol.get_track_flags(track_index)
                    tracks.append(
                        NetMDTrack(
                            index=track_index,
                            title=protocol.get_track_title(track_index),
                            duration_seconds=duration_to_seconds(
                                protocol.get_track_length(track_index)
                            ),
                            encoding=ENCODINGS.get(encoding, f"0x{encoding:02x}"),
                            channels=CHANNELS.get(channel_code, 0),
                            protected=track_flags == TRACK_FLAG_PROTECTED,
                            group=groups.get(track_index),
                        )
                    )
                self._disc_flags = protocol.get_disc_flags()
                recorded, total, available = protocol.get_disc_capacity()
                self._recorded_seconds = duration_to_seconds(recorded)
                self._total_seconds = duration_to_seconds(total)
                self._available_seconds = duration_to_seconds(available)
                self._tracks = tuple(tracks)
                self._disc_title = protocol.get_disc_title(raw_title)
                self._metadata_signature = signature
                self._last_full_refresh = now
                self._metadata_dirty = False

        return NetMDSnapshot(
            connected=True,
            disc_present=True,
            playback_state=playback_state,
            current_track=current_track,
            position_seconds=position_seconds,
            disc_title=self._disc_title,
            writable=bool(self._disc_flags & DISC_FLAG_WRITABLE),
            write_protected=bool(self._disc_flags & DISC_FLAG_WRITE_PROTECTED),
            recorded_seconds=self._recorded_seconds,
            total_seconds=self._total_seconds,
            available_seconds=self._available_seconds,
            tracks=self._tracks,
        )

    def play(self) -> None:
        self._run(self._protocol.play)

    def pause(self) -> None:
        self._run(self._protocol.pause)

    def stop(self) -> None:
        self._run(self._protocol.stop)

    def next_track(self) -> None:
        self._run(self._protocol.next_track)

    def previous_track(self) -> None:
        self._run(self._protocol.previous_track)

    def play_track(self, track: int) -> None:
        def operation() -> None:
            self._protocol.goto_track(track)
            self._protocol.play()

        self._run(operation)

    def seek(self, track: int, seconds: float) -> None:
        self._run(self._protocol.goto_time, track, seconds)

    def rename_track(self, track: int, title: str) -> None:
        def operation() -> None:
            self._protocol.cache_toc()
            try:
                self._protocol.set_track_title(track, title)
            finally:
                with suppress(NetMDError, usb1.USBError):
                    self._protocol.sync_toc()
            self._metadata_dirty = True

        self._run(operation)

    def rename_disc(self, title: str) -> None:
        def operation() -> None:
            self._protocol.cache_toc()
            try:
                self._protocol.set_disc_title(title)
            finally:
                with suppress(NetMDError, usb1.USBError):
                    self._protocol.sync_toc()
            self._metadata_dirty = True

        self._run(operation)

    def move_track(self, source: int, destination: int) -> None:
        def operation() -> None:
            self._protocol.move_track(source, destination)
            self._metadata_dirty = True

        self._run(operation)

    def delete_track(self, track: int) -> None:
        def operation() -> None:
            self._protocol.erase_track(track)
            self._metadata_dirty = True

        self._run(operation)
