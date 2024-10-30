"""The ha-gasbuddy component."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from gasbuddy import GasBuddy  # pylint: disable=import-self

# pylint: disable-next=import-error,no-name-in-module
from gasbuddy.exceptions import APIError, LibraryError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_INTERVAL,
    CONF_STATION_ID,
    CONF_UOM,
    CONFIG_VER,
    COORDINATOR,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)

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
    updated_config = config_entry.data.copy()
    if CONF_UOM not in config_entry.data.keys():
        updated_config[CONF_UOM] = True

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    config_entry.add_update_listener(update_listener)
    interval = config_entry.data.get(CONF_INTERVAL)
    coordinator = GasBuddyUpdateCoordinator(hass, interval, config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = {COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    _LOGGER.debug("Attempting to reload entities from the %s integration", DOMAIN)

    original_config = config_entry.data.copy()

    original_config[CONF_INTERVAL] = config_entry.options[CONF_INTERVAL]
    original_config[CONF_UOM] = config_entry.options[CONF_UOM]

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=original_config,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER
    updated_config = config_entry.data.copy()

    # 1 -> 2: Migrate format
    if version == 1:
        _LOGGER.debug("Migrating from version %s", version)

        # Add default unit of measure setting if missing
        if CONF_UOM not in updated_config.keys():
            updated_config[CONF_UOM] = True

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=new_version
        )

    _LOGGER.debug("Migration to version %s complete", CONFIG_VER)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload entities from the %s integration", DOMAIN)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed entities from the %s integration", DOMAIN)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def async_remove_config_entry_device(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    _LOGGER.debug("Removing device from the %s integration", DOMAIN)

    return True


class GasBuddyUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, interval: int, config: ConfigEntry) -> None:
        """Initialize."""
        self._config = config
        self.hass = hass
        self.interval = timedelta(seconds=interval)
        self._data = {}

        _LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=self.interval)

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        station = self._config.data[CONF_STATION_ID]
        try:
            self._data = await GasBuddy(station_id=station).price_lookup()
        except APIError:
            _LOGGER.error("API error when retreiving data.")
            self._data = {}
        except LibraryError:
            _LOGGER.error("Problem parsing API response.")
            self._data = {}
        except Exception as exception:
            raise UpdateFailed() from exception

        return self._data
