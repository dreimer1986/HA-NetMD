"""Shared NetMD entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetMDCoordinator


class NetMDEntity(CoordinatorEntity[NetMDCoordinator]):
    """Base class for entities belonging to a NetMD player."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetMDCoordinator, suffix: str) -> None:
        super().__init__(coordinator)
        info = coordinator.hub.device_info
        self._attr_unique_id = f"{info.stable_id}-{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.stable_id)},
            manufacturer="Sony" if info.vendor_id == 0x054C else "Sharp",
            model=info.model,
            name=info.model,
        )
