"""The ha-gasbuddy component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from gasbuddy import GasBuddy  # pylint: disable=import-self

# pylint: disable-next=import-error,no-name-in-module
from gasbuddy.exceptions import (
    APIError,
    LibraryError,
)

from .const import (
    CONF_INTERVAL,
    CONF_STATION_ID,
    COORDINATOR,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config: Config
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

    config_entry.add_update_listener(update_listener)
    interval = config_entry.data.get(CONF_INTERVAL)
    coordinator = GasBuddyUpdateCoordinator(hass, interval, config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = {COORDINATOR: coordinator}

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    _LOGGER.debug("Attempting to reload entities from the %s integration", DOMAIN)

    if config_entry.data[CONF_INTERVAL] == config_entry.options[CONF_INTERVAL]:
        _LOGGER.debug("No changes detected not reloading entities.")
        return

    config_entry.data[CONF_INTERVAL] = config_entry.options[CONF_INTERVAL]

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=config_entry.data,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)


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
