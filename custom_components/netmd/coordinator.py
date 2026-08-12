"""Data coordinator for NetMD."""

from __future__ import annotations

import logging
from datetime import timedelta

import usb1
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .hub import NetMDHub
from .models import NetMDSnapshot
from .protocol import NetMDError

_LOGGER = logging.getLogger(__name__)


class NetMDCoordinator(DataUpdateCoordinator[NetMDSnapshot]):
    """Coordinate blocking USB reads through Home Assistant's executor."""

    def __init__(self, hass: HomeAssistant, hub: NetMDHub) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.hub = hub

    async def _async_update_data(self) -> NetMDSnapshot:
        try:
            return await self.hass.async_add_executor_job(self.hub.update)
        except (NetMDError, usb1.USBError) as err:
            raise UpdateFailed(str(err)) from err

    async def async_run_command(self, command, *args) -> None:
        """Run a serialized USB command and immediately refresh state."""
        await self.hass.async_add_executor_job(command, *args)
        await self.async_request_refresh()
