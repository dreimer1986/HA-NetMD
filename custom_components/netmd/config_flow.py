"""Config flow for native NetMD USB devices."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import Any

import usb1
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.usb import UsbServiceInfo

from .const import (
    CONF_ADDRESS,
    CONF_BUS,
    CONF_MODEL,
    CONF_PRODUCT_ID,
    CONF_SERIAL_NUMBER,
    CONF_VENDOR_ID,
    DOMAIN,
)
from .hub import NetMDHub
from .models import NetMDDeviceInfo
from .protocol import USB_MODELS, NetMDError, discover_devices

CONF_DEVICE = "device"

_LOGGER = logging.getLogger(__name__)


def _entry_data(info: NetMDDeviceInfo) -> dict[str, Any]:
    return {
        CONF_VENDOR_ID: info.vendor_id,
        CONF_PRODUCT_ID: info.product_id,
        CONF_BUS: info.bus,
        CONF_ADDRESS: info.address,
        CONF_MODEL: info.model,
        CONF_SERIAL_NUMBER: info.serial_number,
    }


def _parse_usb_number(value: str | int) -> int:
    return int(value, 16) if isinstance(value, str) else value


class NetMDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NetMD."""

    VERSION = 1

    def __init__(self) -> None:
        self._devices: dict[str, NetMDDeviceInfo] = {}
        self._discovered: NetMDDeviceInfo | None = None

    async def _async_test(self, info: NetMDDeviceInfo) -> str | None:
        hub = NetMDHub(info)
        try:
            await self.hass.async_add_executor_job(hub.update)
        except usb1.USBErrorAccess:
            _LOGGER.exception("USB access denied while testing %s", info.model)
            return "usb_permission"
        except (NetMDError, usb1.USBError):
            _LOGGER.exception("NetMD communication test failed for %s", info.model)
            return "cannot_connect"
        finally:
            await self.hass.async_add_executor_job(hub.close)
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Scan for and configure an attached NetMD device."""
        errors: dict[str, str] = {}
        if not self._devices:
            devices = await self.hass.async_add_executor_job(discover_devices)
            self._devices = {device.stable_id: device for device in devices}

        if user_input is not None:
            info = self._devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(info.stable_id)
            self._abort_if_unique_id_configured()
            if error := await self._async_test(info):
                errors["base"] = error
            else:
                return self.async_create_entry(title=info.model, data=_entry_data(info))

        if not self._devices:
            errors["base"] = "no_devices"
            schema = vol.Schema({})
        else:
            options = {
                key: f"{device.model} (USB {device.bus:03d}:{device.address:03d})"
                for key, device in self._devices.items()
            }
            schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_usb(self, discovery_info: UsbServiceInfo):
        """Handle Home Assistant USB discovery."""
        vendor_id = _parse_usb_number(discovery_info.vid)
        product_id = _parse_usb_number(discovery_info.pid)
        path = PurePosixPath(discovery_info.device)
        try:
            bus, address = int(path.parts[-2]), int(path.parts[-1])
        except (IndexError, ValueError):
            bus, address = 0, 0
        self._discovered = NetMDDeviceInfo(
            vendor_id=vendor_id,
            product_id=product_id,
            bus=bus,
            address=address,
            model=USB_MODELS.get(
                (vendor_id, product_id), discovery_info.description or "NetMD"
            ),
            serial_number=discovery_info.serial_number,
        )
        await self.async_set_unique_id(self._discovered.stable_id)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": self._discovered.model}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm a discovered NetMD device."""
        if self._discovered is None:
            return self.async_abort(reason="cannot_connect")
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._async_test(self._discovered):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=self._discovered.model,
                    data=_entry_data(self._discovered),
                )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"model": self._discovered.model},
        )
