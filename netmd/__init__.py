"""Native Python NetMD integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONF_BUS,
    CONF_MODEL,
    CONF_PRODUCT_ID,
    CONF_SERIAL_NUMBER,
    CONF_VENDOR_ID,
    PLATFORMS,
)
from .coordinator import NetMDCoordinator
from .hub import NetMDHub
from .models import NetMDDeviceInfo

type NetMDConfigEntry = ConfigEntry[NetMDCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NetMDConfigEntry) -> bool:
    """Set up NetMD from a config entry."""
    info = NetMDDeviceInfo(
        vendor_id=entry.data[CONF_VENDOR_ID],
        product_id=entry.data[CONF_PRODUCT_ID],
        bus=entry.data[CONF_BUS],
        address=entry.data[CONF_ADDRESS],
        model=entry.data[CONF_MODEL],
        serial_number=entry.data.get(CONF_SERIAL_NUMBER),
    )
    coordinator = NetMDCoordinator(hass, NetMDHub(info))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetMDConfigEntry) -> bool:
    """Unload a NetMD config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await hass.async_add_executor_job(entry.runtime_data.hub.close)
    return True
