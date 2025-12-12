"""The ha-gasbuddy component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_GPS,
    CONF_INTERVAL,
    CONF_SOLVER,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    COORDINATOR,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)
from .coordinator import GasBuddyUpdateCoordinator
from .services import GasBuddyServices

_LOGGER = logging.getLogger(__name__)


async def async_setup(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config: ConfigType
) -> bool:
    """Disallow configuration via YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up is called when Home Assistant is loading our component."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )

    # Some sanity checks
    updated_config = config_entry.options.copy()
    if CONF_UOM not in config_entry.options:
        updated_config[CONF_UOM] = True
    if CONF_GPS not in config_entry.options:
        updated_config[CONF_GPS] = True
    if CONF_INTERVAL not in config_entry.options:
        updated_config[CONF_INTERVAL] = 3600

    if updated_config != config_entry.options:
        hass.config_entries.async_update_entry(config_entry, options=updated_config)

    config_entry.add_update_listener(update_listener)
    coordinator = GasBuddyUpdateCoordinator(hass, config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = {COORDINATOR: coordinator}

    services = GasBuddyServices(hass, config_entry)
    services.async_register()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    _LOGGER.debug("Attempting to reload entities from the %s integration", DOMAIN)

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER
    updated_config = config_entry.data.copy()

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Migrate format
    if version == 1:
        # Add default unit of measure setting if missing
        if CONF_UOM not in updated_config:
            updated_config[CONF_UOM] = True

    if version < 5:
        if CONF_GPS not in updated_config:
            updated_config[CONF_GPS] = True

    if version < 6:
        if CONF_SOLVER not in updated_config:
            updated_config[CONF_SOLVER] = None

    if version < 7:
        if CONF_TIMEOUT not in updated_config:
            updated_config[CONF_TIMEOUT] = 60000

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=new_version
        )

    _LOGGER.debug("Migration to version %s complete", CONFIG_VER)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload entities from the %s integration", DOMAIN)

    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload_ok:
        _LOGGER.debug("Successfully removed entities from the %s integration", DOMAIN)

    return unload_ok


async def async_remove_config_entry_device(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    _LOGGER.debug("Removing device from the %s integration", DOMAIN)

    return True
