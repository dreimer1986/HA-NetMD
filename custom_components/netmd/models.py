"""Data models for NetMD devices."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NetMDDeviceInfo:
    """A discovered NetMD USB device."""

    vendor_id: int
    product_id: int
    bus: int
    address: int
    model: str
    serial_number: str | None = None

    @property
    def stable_id(self) -> str:
        """Return the best available identifier for this device."""
        suffix = self.serial_number or f"bus{self.bus}-address{self.address}"
        return f"{self.vendor_id:04x}:{self.product_id:04x}:{suffix}"


@dataclass(frozen=True, slots=True)
class NetMDTrack:
    """A track stored on a MiniDisc."""

    index: int
    title: str
    duration_seconds: float
    encoding: str
    channels: int
    protected: bool
    group: str | None = None

    @property
    def display_name(self) -> str:
        """Return a friendly, unique source name."""
        return f"{self.index + 1:02d} — {self.title or 'Untitled'}"


@dataclass(frozen=True, slots=True)
class NetMDSnapshot:
    """Current state of a NetMD device and its disc."""

    connected: bool
    disc_present: bool
    playback_state: str = "stopped"
    current_track: int | None = None
    position_seconds: float | None = None
    disc_title: str = ""
    writable: bool = False
    write_protected: bool = False
    recorded_seconds: float | None = None
    total_seconds: float | None = None
    available_seconds: float | None = None
    tracks: tuple[NetMDTrack, ...] = field(default_factory=tuple)
