"""Provide diagnostics for GasBuddy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_POSTAL, CONF_SOLVER, COORDINATOR, DOMAIN

REDACT_KEYS = {
    CONF_SOLVER,
    CONF_POSTAL,
    "latitude",
    "longitude",
    "street_address",
    "ev_station_address",
    "city",
    "state",
    "zip",
    "phone",
    "address",
    "station_id",
    "id",
    "station_code",
    "station_identifier",
    "station_number",
    "uid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    diag["config"] = config_entry.as_dict()
    coordinator = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get(COORDINATOR)
    if coordinator is not None:
        diag["coordinator_data"] = coordinator.data or {}
    return async_redact_data(diag, REDACT_KEYS)


async def async_get_device_diagnostics(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    return async_redact_data(coordinator.data or {}, REDACT_KEYS)
