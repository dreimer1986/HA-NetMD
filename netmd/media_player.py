"""Media player platform for NetMD."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import voluptuous as vol
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NetMDCoordinator
from .entity import NetMDEntity

SERVICE_RENAME_TRACK = "rename_track"
SERVICE_RENAME_DISC = "rename_disc"
SERVICE_MOVE_TRACK = "move_track"
SERVICE_DELETE_TRACK = "delete_track"
SERVICE_PLAY_TRACK = "play_track"

ATTR_TRACK_NUMBER = "track_number"
ATTR_SOURCE_TRACK_NUMBER = "source_track_number"
ATTR_DESTINATION_TRACK_NUMBER = "destination_track_number"
ATTR_TITLE = "title"

TRACK_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=255))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NetMDCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NetMD media player."""
    async_add_entities([NetMDMediaPlayer(entry.runtime_data)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RENAME_TRACK,
        {
            vol.Required(ATTR_TRACK_NUMBER): TRACK_SCHEMA,
            vol.Required(ATTR_TITLE): cv.string,
        },
        "async_rename_track",
    )
    platform.async_register_entity_service(
        SERVICE_RENAME_DISC,
        {vol.Required(ATTR_TITLE): cv.string},
        "async_rename_disc",
    )
    platform.async_register_entity_service(
        SERVICE_MOVE_TRACK,
        {
            vol.Required(ATTR_SOURCE_TRACK_NUMBER): TRACK_SCHEMA,
            vol.Required(ATTR_DESTINATION_TRACK_NUMBER): TRACK_SCHEMA,
        },
        "async_move_track",
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_TRACK,
        {vol.Required(ATTR_TRACK_NUMBER): TRACK_SCHEMA},
        "async_delete_track",
    )
    platform.async_register_entity_service(
        SERVICE_PLAY_TRACK,
        {vol.Required(ATTR_TRACK_NUMBER): TRACK_SCHEMA},
        "async_play_track",
    )


class NetMDMediaPlayer(NetMDEntity, MediaPlayerEntity):
    """Represent the attached NetMD recorder/player."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: NetMDCoordinator) -> None:
        super().__init__(coordinator, "player")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.connected

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data
        if not data.disc_present:
            return MediaPlayerState.IDLE
        return {
            "playing": MediaPlayerState.PLAYING,
            "paused": MediaPlayerState.PAUSED,
        }.get(data.playback_state, MediaPlayerState.IDLE)

    @property
    def media_title(self) -> str | None:
        track = self._current_track
        return track.title if track else None

    @property
    def media_duration(self) -> float | None:
        track = self._current_track
        return track.duration_seconds if track else None

    @property
    def media_position(self) -> float | None:
        return self.coordinator.data.position_seconds

    @property
    def media_position_updated_at(self) -> datetime | None:
        return datetime.now(UTC) if self.media_position is not None else None

    @property
    def source(self) -> str | None:
        track = self._current_track
        return track.display_name if track else None

    @property
    def source_list(self) -> list[str]:
        return [track.display_name for track in self.coordinator.data.tracks]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        track = self._current_track
        return {
            "disc_title": data.disc_title,
            "disc_present": data.disc_present,
            "writable": data.writable,
            "write_protected": data.write_protected,
            "track_count": len(data.tracks),
            "track_number": track.index + 1 if track else None,
            "encoding": track.encoding if track else None,
            "channels": track.channels if track else None,
            "group": track.group if track else None,
            "protected": track.protected if track else None,
        }

    @property
    def _current_track(self):
        index = self.coordinator.data.current_track
        tracks = self.coordinator.data.tracks
        return tracks[index] if index is not None and 0 <= index < len(tracks) else None

    def _track_index(self, one_based: int) -> int:
        if not 1 <= one_based <= len(self.coordinator.data.tracks):
            raise ValueError(
                f"Track must be between 1 and {len(self.coordinator.data.tracks)}"
            )
        return one_based - 1

    async def async_media_play(self) -> None:
        await self.coordinator.async_run_command(self.coordinator.hub.play)

    async def async_media_pause(self) -> None:
        await self.coordinator.async_run_command(self.coordinator.hub.pause)

    async def async_media_stop(self) -> None:
        await self.coordinator.async_run_command(self.coordinator.hub.stop)

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_run_command(self.coordinator.hub.next_track)

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_run_command(self.coordinator.hub.previous_track)

    async def async_media_seek(self, position: float) -> None:
        track = self.coordinator.data.current_track
        if track is None:
            raise ValueError("No current track")
        await self.coordinator.async_run_command(
            self.coordinator.hub.seek, track, position
        )

    async def async_select_source(self, source: str) -> None:
        track = next(
            (
                item
                for item in self.coordinator.data.tracks
                if item.display_name == source
            ),
            None,
        )
        if track is None:
            raise ValueError(f"Unknown track: {source}")
        await self.coordinator.async_run_command(
            self.coordinator.hub.play_track, track.index
        )

    async def async_rename_track(self, track_number: int, title: str) -> None:
        await self.coordinator.async_run_command(
            self.coordinator.hub.rename_track,
            self._track_index(track_number),
            title,
        )

    async def async_rename_disc(self, title: str) -> None:
        await self.coordinator.async_run_command(
            self.coordinator.hub.rename_disc, title
        )

    async def async_move_track(
        self, source_track_number: int, destination_track_number: int
    ) -> None:
        await self.coordinator.async_run_command(
            self.coordinator.hub.move_track,
            self._track_index(source_track_number),
            self._track_index(destination_track_number),
        )

    async def async_delete_track(self, track_number: int) -> None:
        await self.coordinator.async_run_command(
            self.coordinator.hub.delete_track,
            self._track_index(track_number),
        )

    async def async_play_track(self, track_number: int) -> None:
        await self.coordinator.async_run_command(
            self.coordinator.hub.play_track,
            self._track_index(track_number),
        )
