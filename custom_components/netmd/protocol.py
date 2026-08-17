"""Native Python implementation of the NetMD USB control protocol.

The protocol commands are based on NetMDPython from linux-minidisc.
Copyright (C) the linux-minidisc contributors. This adaptation was rewritten
for Python 3 and Home Assistant and is licensed under GPL-2.0-or-later.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from contextlib import contextmanager, suppress
from typing import Any, ClassVar

import usb1

from .models import NetMDDeviceInfo

USB_MODELS: dict[tuple[int, int], str] = {
    (0x054C, 0x0034): "Sony PCLK-XX",
    (0x054C, 0x0036): "Sony NetMD",
    (0x054C, 0x0075): "Sony MZ-N1",
    (0x054C, 0x007C): "Sony NetMD",
    (0x054C, 0x0080): "Sony LAM-1",
    (0x054C, 0x0081): "Sony MDS-JE780/JB980",
    (0x054C, 0x0084): "Sony MZ-N505",
    (0x054C, 0x0085): "Sony MZ-S1",
    (0x054C, 0x0086): "Sony MZ-N707",
    (0x054C, 0x008E): "Sony CMT-C7NT",
    (0x054C, 0x0097): "Sony PCGA-MDN1",
    (0x054C, 0x00AD): "Sony CMT-L7HD",
    (0x054C, 0x00C6): "Sony MZ-N10",
    (0x054C, 0x00C7): "Sony MZ-N910",
    (0x054C, 0x00C8): "Sony MZ-N710/NE810/NF810",
    (0x054C, 0x00C9): "Sony MZ-N510/NF610",
    (0x054C, 0x00CA): "Sony MZ-NE410/DN430/NF520",
    (0x054C, 0x00E7): "Sony CMT-M333NT/M373NT",
    (0x054C, 0x00EB): "Sony MZ-NE810/NE910",
    (0x054C, 0x0101): "Sony LAM-10",
    (0x054C, 0x0113): "Aiwa AM-NX1",
    (0x054C, 0x014C): "Aiwa AM-NX9",
    (0x054C, 0x017E): "Sony MZ-NH1",
    (0x054C, 0x0180): "Sony MZ-NH3D",
    (0x054C, 0x0182): "Sony MZ-NH900",
    (0x054C, 0x0184): "Sony MZ-NH700/800",
    (0x054C, 0x0186): "Sony MZ-NH600/600D",
    (0x054C, 0x0188): "Sony MZ-N920",
    (0x054C, 0x018A): "Sony LAM-3",
    (0x054C, 0x01E9): "Sony MZ-DH10P",
    (0x054C, 0x0219): "Sony MZ-RH10",
    (0x054C, 0x021B): "Sony MZ-RH710/RH910/M10",
    (0x054C, 0x021D): "Sony CMT-AH10",
    (0x054C, 0x022C): "Sony CMT-AH10",
    (0x054C, 0x023C): "Sony DS-HMD1",
    (0x054C, 0x0286): "Sony MZ-RH1",
    (0x04DD, 0x7202): "Sharp IM-MT880H/MT899H",
    (0x04DD, 0x9013): "Sharp IM-DR400/DR410",
    (0x04DD, 0x9014): "Sharp IM-DR80/DR420/DR580",
}

STATUS_NOT_IMPLEMENTED = 0x08
STATUS_ACCEPTED = 0x09
STATUS_REJECTED = 0x0A
STATUS_IMPLEMENTED = 0x0C
STATUS_INTERIM = 0x0F

OPERATING_STATUS_PLAYING = 0xC375
OPERATING_STATUS_PAUSED = 0xC37D
OPERATING_STATUS_FAST_FORWARDING = 0xC33F
OPERATING_STATUS_REWINDING = 0xC34F
OPERATING_STATUS_STOPPED = 0xC5FF

DISC_FLAG_WRITABLE = 0x10
DISC_FLAG_WRITE_PROTECTED = 0x40
TRACK_FLAG_PROTECTED = 0x03

DESCRIPTOR_DISC_TITLE = b"\x10\x18\x01"
DESCRIPTOR_AUDIO_UTOC_1 = b"\x10\x18\x02"
DESCRIPTOR_AUDIO_CONTENTS = b"\x10\x10\x01"
DESCRIPTOR_ROOT = b"\x10\x10\x00"
DESCRIPTOR_OPERATING_STATUS = b"\x80\x00"

DESCRIPTOR_CLOSE = 0x00
DESCRIPTOR_OPEN_READ = 0x01
DESCRIPTOR_OPEN_WRITE = 0x03

ENCODINGS = {0x90: "SP", 0x92: "LP2", 0x93: "LP4"}
CHANNELS = {0x01: 1, 0x00: 2}


class NetMDError(Exception):
    """Base error raised by the native NetMD implementation."""


class NetMDNotFoundError(NetMDError):
    """The configured NetMD device is not connected."""


class NetMDRejectedError(NetMDError):
    """The NetMD device rejected a command."""


class NetMDProtocolError(NetMDError):
    """The NetMD device returned an invalid or unsupported response."""


def bcd_to_int(value: int) -> int:
    """Convert a binary-coded decimal value to an integer."""
    result = 0
    multiplier = 1
    while value:
        result += (value & 0x0F) * multiplier
        value >>= 4
        multiplier *= 10
    return result


def int_to_bcd(value: int, length: int = 1) -> int:
    """Convert a non-negative integer to binary-coded decimal."""
    if value < 0 or value >= 10 ** (length * 2):
        raise ValueError(f"Value {value} does not fit in {length} BCD byte(s)")
    result = 0
    shift = 0
    while value:
        value, digit = divmod(value, 10)
        result |= digit << shift
        shift += 4
    return result


class QueryCodec:
    """Encode and decode linux-minidisc's compact query notation."""

    _LENGTHS: ClassVar[dict[str, int]] = {"b": 1, "w": 2, "d": 4, "q": 8}

    @classmethod
    def format(cls, template: str, *args: int | bytes | str) -> bytes:
        """Build a protocol message from a compact format template."""
        output = bytearray()
        arguments = iter(args)
        compact = "".join(template.split())
        index = 0
        while index < len(compact):
            if compact[index] != "%":
                output.append(int(compact[index : index + 2], 16))
                index += 2
                continue
            code = compact[index + 1]
            value = next(arguments)
            index += 2
            if code in cls._LENGTHS:
                if not isinstance(value, int):
                    raise TypeError(f"%{code} requires int")
                output.extend(value.to_bytes(cls._LENGTHS[code], "big"))
            elif code in {"s", "x", "*"}:
                raw = (
                    value.encode("shift_jis", errors="replace")
                    if isinstance(value, str)
                    else bytes(value)
                )
                if code in {"s", "x"}:
                    length = len(raw) + (1 if code == "s" else 0)
                    output.extend(length.to_bytes(2, "big"))
                output.extend(raw)
                if code == "s":
                    output.append(0)
            else:
                raise ValueError(f"Unknown format code %{code}")
        try:
            next(arguments)
        except StopIteration:
            return bytes(output)
        raise ValueError("Too many query arguments")

    @classmethod
    def scan(cls, data: bytes, template: str) -> list[int | bytes]:
        """Validate and extract fields from a protocol response."""
        result: list[int | bytes] = []
        compact = "".join(template.split())
        source_index = 0
        template_index = 0
        while template_index < len(compact):
            if compact[template_index] != "%":
                expected = int(compact[template_index : template_index + 2], 16)
                if source_index >= len(data) or data[source_index] != expected:
                    actual = data[source_index] if source_index < len(data) else None
                    raise NetMDProtocolError(
                        f"Response mismatch at byte {source_index}: expected {expected:02x}, got {actual!r}"
                    )
                source_index += 1
                template_index += 2
                continue
            code = compact[template_index + 1]
            template_index += 2
            if code == "?":
                if source_index >= len(data):
                    raise NetMDProtocolError("Response ended at wildcard field")
                source_index += 1
            elif code in cls._LENGTHS:
                length = cls._LENGTHS[code]
                if source_index + length > len(data):
                    raise NetMDProtocolError(f"Response ended in %{code} field")
                result.append(
                    int.from_bytes(data[source_index : source_index + length], "big")
                )
                source_index += length
            elif code in {"s", "x"}:
                if source_index + 2 > len(data):
                    raise NetMDProtocolError(f"Response ended before %{code} length")
                length = int.from_bytes(data[source_index : source_index + 2], "big")
                source_index += 2
                if source_index + length > len(data):
                    raise NetMDProtocolError(f"Response ended in %{code} field")
                value = data[source_index : source_index + length]
                source_index += length
                result.append(value[:-1] if code == "s" else value)
            elif code == "*":
                result.append(data[source_index:])
                source_index = len(data)
            else:
                raise ValueError(f"Unknown scan code %{code}")
        if source_index != len(data):
            raise NetMDProtocolError(
                f"Response contains {len(data) - source_index} unexpected byte(s)"
            )
        return result


def _safe_serial(device: Any) -> str | None:
    handle = None
    try:
        handle = device.open()
        value = handle.getSerialNumber()
        return value or None
    except (usb1.USBError, UnicodeDecodeError):
        return None
    finally:
        if handle is not None:
            handle.close()


def discover_devices() -> list[NetMDDeviceInfo]:
    """Return all supported NetMD devices currently visible through libusb."""
    found: list[NetMDDeviceInfo] = []
    with usb1.USBContext() as context:
        for device in context.getDeviceList(skip_on_error=True):
            key = (device.getVendorID(), device.getProductID())
            if key not in USB_MODELS:
                continue
            found.append(
                NetMDDeviceInfo(
                    vendor_id=key[0],
                    product_id=key[1],
                    bus=device.getBusNumber(),
                    address=device.getDeviceAddress(),
                    model=USB_MODELS[key],
                    serial_number=_safe_serial(device),
                )
            )
    return found


class NetMDTransport:
    """Synchronous libusb transport for one NetMD device."""

    def __init__(self, device_info: NetMDDeviceInfo) -> None:
        self.device_info = device_info
        self._context: usb1.USBContext | None = None
        self._handle: Any | None = None

    def open(self) -> None:
        """Open and claim the configured USB device."""
        self.close()
        context = usb1.USBContext()
        candidates = [
            device
            for device in context.getDeviceList(skip_on_error=True)
            if (device.getVendorID(), device.getProductID())
            == (
                self.device_info.vendor_id,
                self.device_info.product_id,
            )
        ]
        selected = None
        if self.device_info.serial_number:
            selected = next(
                (
                    device
                    for device in candidates
                    if _safe_serial(device) == self.device_info.serial_number
                ),
                None,
            )
        else:
            selected = next(
                (
                    device
                    for device in candidates
                    if device.getBusNumber() == self.device_info.bus
                    and device.getDeviceAddress() == self.device_info.address
                ),
                None,
            )
            if selected is None and len(candidates) == 1:
                selected = candidates[0]
        if selected is not None:
            device = selected
            handle = device.open()
            try:
                handle.setAutoDetachKernelDriver(True)
            except usb1.USBError:
                pass
            try:
                handle.setConfiguration(1)
            except usb1.USBErrorBusy:
                pass
            handle.claimInterface(0)
            self._context = context
            self._handle = handle
            if self._reply_length():
                self.read_reply()
            return
        context.close()
        raise NetMDNotFoundError(f"{self.device_info.model} is not connected")

    def close(self) -> None:
        """Release the USB interface without resetting the player."""
        if self._handle is not None:
            try:
                self._handle.releaseInterface(0)
            except usb1.USBError:
                pass
            self._handle.close()
            self._handle = None
        if self._context is not None:
            self._context.close()
            self._context = None

    def _require_handle(self) -> Any:
        if self._handle is None:
            raise NetMDNotFoundError("NetMD USB connection is closed")
        return self._handle

    def _reply_length(self) -> int:
        reply = self._require_handle().controlRead(0xC1, 0x01, 0, 0, 4, timeout=1000)
        if len(reply) < 3:
            raise NetMDProtocolError("Short NetMD reply-length response")
        return reply[2]

    def send(self, command: bytes) -> None:
        self._require_handle().controlWrite(0x41, 0x80, 0, 0, command, timeout=1000)

    def read_reply(self, timeout: float = 5.0) -> bytes:
        deadline = time.monotonic() + timeout
        length = 0
        while not length and time.monotonic() < deadline:
            length = self._reply_length()
            if not length:
                time.sleep(0.05)
        if not length:
            raise NetMDProtocolError("Timed out waiting for NetMD response")
        return bytes(
            self._require_handle().controlRead(0xC1, 0x81, 0, 0, length, timeout=5000)
        )


class NetMDProtocol:
    """High-level NetMD protocol operations used by Home Assistant."""

    def __init__(self, transport: NetMDTransport) -> None:
        self.transport = transport

    def query(
        self, template: str, *args: int | bytes | str, test: bool = False
    ) -> bytes:
        payload = QueryCodec.format(template, *args)
        self.transport.send(bytes([0x02 if test else 0x00]) + payload)
        for _attempt in range(10):
            response = self.transport.read_reply()
            if not response:
                raise NetMDProtocolError("Empty NetMD response")
            if response[0] == STATUS_REJECTED:
                raise NetMDRejectedError("NetMD rejected the command")
            if response[0] == STATUS_NOT_IMPLEMENTED:
                raise NetMDProtocolError("NetMD does not implement the command")
            if response[0] == STATUS_INTERIM:
                time.sleep(0.05)
                continue
            if response[0] not in {STATUS_ACCEPTED, STATUS_IMPLEMENTED}:
                raise NetMDProtocolError(
                    f"Unknown NetMD response status 0x{response[0]:02x}"
                )
            return response[1:]
        raise NetMDProtocolError("NetMD remained in interim state")

    def change_descriptor_state(self, descriptor: bytes, action: int) -> None:
        """Open or close a NetMD descriptor."""
        self.query("1808 %* %b 00", descriptor, action)

    @contextmanager
    def descriptor(self, descriptor: bytes, action: int = DESCRIPTOR_OPEN_READ):
        """Open a descriptor for one operation and always close it."""
        opened = False
        try:
            self.change_descriptor_state(descriptor, action)
            opened = True
        except (NetMDError, usb1.USBError):
            # Older libnetmd did not open descriptors explicitly and several
            # players reject these state changes while accepting the actual
            # read/write command.
            pass
        try:
            yield
        finally:
            if opened:
                with suppress(NetMDError, usb1.USBError):
                    self.change_descriptor_state(descriptor, DESCRIPTOR_CLOSE)

    def get_status(self) -> bytes:
        with self.descriptor(DESCRIPTOR_OPERATING_STATUS):
            response = self.query("1809 8001 0230 8800 0030 8804 00 ff00 00000000")
            return QueryCodec.scan(
                response,
                "1809 8001 0230 8800 0030 8804 00 1000 00090000 %x",
            )[0]  # type: ignore[return-value]

    def is_disc_present(self) -> bool:
        status = self.get_status()
        return len(status) > 4 and status[4] == 0x40

    def get_operating_status(self) -> int:
        with self.descriptor(DESCRIPTOR_OPERATING_STATUS):
            response = self.query(
                "1809 8001 0330 8802 0030 8805 0030 8806 00 ff00 00000000"
            )
            raw = QueryCodec.scan(
                response,
                "1809 8001 0330 %?%? %?%? %?%? %?%? %?%? %? 1000 00%?0000 %x %*",
            )[0]
            if not isinstance(raw, bytes) or len(raw) < 6:
                raise NetMDProtocolError("Invalid operating-status response")
            return int.from_bytes(raw[4:6], "big")

    def get_position(self) -> tuple[int, int, int, int, int] | None:
        with self.descriptor(DESCRIPTOR_OPERATING_STATUS):
            try:
                response = self.query(
                    "1809 8001 0430 8802 0030 8805 0030 0003 0030 0002 00 ff00 00000000"
                )
            except NetMDRejectedError:
                return None
            values = QueryCodec.scan(
                response,
                "1809 8001 0430 %?%? %?%? %?%? %?%? %?%? %?%? %?%? %? %?00 "
                "00%?0000 000b 0002 0007 00 %w %b %b %b %b",
            )
        track = int(values[0])
        return (track, *(bcd_to_int(int(value)) for value in values[1:]))

    def _play(self, action: int) -> None:
        response = self.query("18c3 ff %b 000000", action)
        QueryCodec.scan(response, "18c3 00 %b 000000")

    def play(self) -> None:
        self._play(0x75)

    def pause(self) -> None:
        self._play(0x7D)

    def fast_forward(self) -> None:
        self._play(0x39)

    def rewind(self) -> None:
        self._play(0x49)

    def stop(self) -> None:
        QueryCodec.scan(self.query("18c5 ff 00000000"), "18c5 00 00000000")

    def goto_track(self, track: int) -> None:
        QueryCodec.scan(
            self.query("1850 ff010000 0000 %w", track), "1850 00010000 0000 %w"
        )

    def goto_time(self, track: int, seconds: float) -> None:
        seconds_int = max(0, int(seconds))
        hour, remainder = divmod(seconds_int, 3600)
        minute, second = divmod(remainder, 60)
        frame = max(0, min(99, round((seconds - seconds_int) * 100)))
        response = self.query(
            "1850 ff000000 0000 %w %b%b%b%b",
            track,
            int_to_bcd(hour),
            int_to_bcd(minute),
            int_to_bcd(second),
            int_to_bcd(frame),
        )
        QueryCodec.scan(response, "1850 00000000 %?%? %w %b%b%b%b")

    def _track_change(self, direction: int) -> None:
        QueryCodec.scan(
            self.query("1850 ff10 00000000 %w", direction),
            "1850 0010 00000000 %?%?",
        )

    def next_track(self) -> None:
        self._track_change(0x8001)

    def previous_track(self) -> None:
        self._track_change(0x0002)

    def get_disc_flags(self) -> int:
        with self.descriptor(DESCRIPTOR_ROOT):
            response = self.query("1806 01101000 ff00 0001000b")
            return int(QueryCodec.scan(response, "1806 01101000 1000 0001000b %b")[0])

    def get_track_count(self) -> int:
        with self.descriptor(DESCRIPTOR_AUDIO_CONTENTS):
            response = self.query("1806 02101001 3000 1000 ff00 00000000")
            return int(
                QueryCodec.scan(
                    response,
                    "1806 02101001 %?%? %?%? 1000 00%?0000 0006 0010000200%b",
                )[0]
            )

    def get_raw_disc_title(self) -> str:
        done = 0
        remaining = 0
        total = 1
        chunks: list[bytes] = []
        with (
            self.descriptor(DESCRIPTOR_AUDIO_CONTENTS),
            self.descriptor(DESCRIPTOR_DISC_TITLE),
        ):
            while done < total:
                response = self.query(
                    "1806 02201801 0000 3000 0a00 ff00 %w%w", remaining, done
                )
                if remaining == 0:
                    chunk_size, total, chunk = QueryCodec.scan(
                        response,
                        "1806 02201801 00%? 3000 0a00 1000 %w0000 %?%?000a %w %*",
                    )
                    chunk_size = int(chunk_size) - 6
                else:
                    chunk_size, chunk = QueryCodec.scan(
                        response,
                        "1806 02201801 00%? 3000 0a00 1000 %w%?%? %*",
                    )
                if not isinstance(chunk, bytes) or int(chunk_size) != len(chunk):
                    raise NetMDProtocolError("Invalid disc-title chunk")
                chunks.append(chunk)
                done += int(chunk_size)
                remaining = int(total) - done
        return b"".join(chunks).rstrip(b"\0").decode("shift_jis", errors="replace")

    def get_disc_title(self, raw: str | None = None) -> str:
        raw = self.get_raw_disc_title() if raw is None else raw
        if raw.endswith("//"):
            first = raw.split("//", 1)[0]
            return first[2:] if first.startswith("0;") else ""
        return raw

    def get_groups(
        self, track_count: int, raw_title: str | None = None
    ) -> dict[int, str]:
        raw = self.get_raw_disc_title() if raw_title is None else raw_title
        groups: dict[int, str] = {}
        for item in raw.split("//"):
            if not item or item.startswith("0;") or ";" not in item:
                continue
            track_range, name = item.split(";", 1)
            try:
                first_text, last_text = (track_range.split("-", 1) + [track_range])[:2]
                first, last = int(first_text), int(last_text)
            except ValueError:
                continue
            for one_based in range(max(1, first), min(track_count, last) + 1):
                groups[one_based - 1] = name
        return groups

    def get_track_title(self, track: int) -> str:
        with self.descriptor(DESCRIPTOR_AUDIO_UTOC_1):
            response = self.query("1806 02201802 %w 3000 0a00 ff00 00000000", track)
            raw = QueryCodec.scan(
                response,
                "1806 022018%? %?%? %?%? %?%? 1000 00%?0000 00%?000a %x",
            )[0]
        assert isinstance(raw, bytes)
        return raw.rstrip(b"\0").decode("shift_jis", errors="replace")

    def set_track_title(self, track: int, title: str) -> None:
        old_length = len(
            self.get_track_title(track).encode("shift_jis", errors="replace")
        )
        encoded = title.encode("shift_jis", errors="replace")
        with self.descriptor(DESCRIPTOR_AUDIO_UTOC_1, DESCRIPTOR_OPEN_WRITE):
            response = self.query(
                "1807 02201802 %w 3000 0a00 5000 %w 0000 %w %*",
                track,
                len(encoded),
                old_length,
                encoded,
            )
            QueryCodec.scan(
                response,
                "1807 022018%? %?%? 3000 0a00 5000 %?%? 0000 %?%?",
            )

    def set_raw_disc_title(self, title: str) -> None:
        old_length = len(
            self.get_raw_disc_title().encode("shift_jis", errors="replace")
        )
        encoded = title.encode("shift_jis", errors="replace")
        descriptor = (
            DESCRIPTOR_AUDIO_UTOC_1
            if self.transport.device_info.vendor_id == 0x04DD
            else DESCRIPTOR_DISC_TITLE
        )
        with self.descriptor(descriptor, DESCRIPTOR_OPEN_WRITE):
            response = self.query(
                "1807 02201801 0000 3000 0a00 5000 %w 0000 %w %*",
                len(encoded),
                old_length,
                encoded,
            )
            QueryCodec.scan(
                response,
                "1807 02201801 00%? 3000 0a00 5000 %?%? 0000 %?%?",
            )

    def set_disc_title(self, title: str) -> None:
        raw = self.get_raw_disc_title()
        if raw.endswith("//"):
            parts = raw.split("//")
            if parts and parts[0].startswith("0;"):
                parts[0] = f"0;{title}"
            else:
                parts.insert(0, f"0;{title}")
            raw = "//".join(parts)
        else:
            raw = title
        self.set_raw_disc_title(raw)

    def cache_toc(self) -> None:
        QueryCodec.scan(self.query("1808 10180203 00"), "1808 10180203 00")

    def sync_toc(self) -> None:
        QueryCodec.scan(self.query("1808 10180200 00"), "1808 10180200 00")

    def erase_track(self, track: int) -> None:
        self.query("1840 ff01 00 201001 %w", track)

    def move_track(self, source: int, destination: int) -> None:
        self.query("1843 ff00 00 201001 %w 201001 %w", source, destination)

    def _get_track_info(self, track: int, first: int, second: int) -> bytes:
        with self.descriptor(DESCRIPTOR_AUDIO_CONTENTS):
            response = self.query(
                "1806 02201001 %w %w %w ff00 00000000", track, first, second
            )
            raw = QueryCodec.scan(
                response,
                "1806 02201001 %?%? %?%? %?%? 1000 00%?0000 %x",
            )[0]
        assert isinstance(raw, bytes)
        return raw

    def get_track_length(self, track: int) -> tuple[int, int, int, int]:
        raw = QueryCodec.scan(
            self._get_track_info(track, 0x3000, 0x0100), "0001 0006 0000 %b %b %b %b"
        )
        return tuple(bcd_to_int(int(value)) for value in raw)  # type: ignore[return-value]

    def get_track_encoding(self, track: int) -> tuple[int, int]:
        values = QueryCodec.scan(
            self._get_track_info(track, 0x3080, 0x0700), "8007 0004 0110 %b %b"
        )
        return int(values[0]), int(values[1])

    def get_track_flags(self, track: int) -> int:
        with self.descriptor(DESCRIPTOR_AUDIO_CONTENTS):
            response = self.query("1806 01201001 %w ff00 00010008", track)
            return int(
                QueryCodec.scan(
                    response,
                    "1806 01201001 %?%? 10 00 00010008 %b",
                )[0]
            )

    def get_disc_capacity(self) -> tuple[tuple[int, int, int, int], ...]:
        with self.descriptor(DESCRIPTOR_ROOT):
            response = self.query("1806 02101000 3080 0300 ff00 00000000")
            values = QueryCodec.scan(
                response,
                "1806 02101000 3080 0300 1000 001d0000 001b %?03 0017 8000 "
                "0005 %w %b %b %b 0005 %w %b %b %b 0005 %w %b %b %b",
            )
        result = []
        for offset in range(0, 12, 4):
            result.append(
                tuple(bcd_to_int(int(value)) for value in values[offset : offset + 4])
            )
        return tuple(result)


def duration_to_seconds(value: Iterable[int]) -> float:
    """Convert a NetMD hour/minute/second/frame tuple to seconds."""
    hour, minute, second, frame = value
    return hour * 3600 + minute * 60 + second + frame / 512
