"""Sensor platform for NetMD."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NetMDCoordinator
from .entity import NetMDEntity
from .models import NetMDSnapshot


@dataclass(frozen=True, kw_only=True)
class NetMDSensorDescription(SensorEntityDescription):
    """Describe a NetMD sensor."""

    value_fn: Callable[[NetMDSnapshot], str | int | float | None]


SENSORS = (
    NetMDSensorDescription(
        key="disc_title",
        translation_key="disc_title",
        value_fn=lambda data: data.disc_title or None,
    ),
    NetMDSensorDescription(
        key="track_count",
        translation_key="track_count",
        value_fn=lambda data: len(data.tracks) if data.disc_present else None,
    ),
    NetMDSensorDescription(
        key="recorded_time",
        translation_key="recorded_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.recorded_seconds,
    ),
    NetMDSensorDescription(
        key="available_time",
        translation_key="available_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.available_seconds,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NetMDCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NetMD sensors."""
    async_add_entities(
        NetMDSensor(entry.runtime_data, description) for description in SENSORS
    )


class NetMDSensor(NetMDEntity, SensorEntity):
    """Represent one value read from a MiniDisc."""

    entity_description: NetMDSensorDescription

    def __init__(
        self, coordinator: NetMDCoordinator, description: NetMDSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        return self.entity_description.value_fn(self.coordinator.data)
