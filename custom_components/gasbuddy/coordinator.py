"""Update coordinator for GasBuddy."""

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from py_gasbuddy import GasBuddy

# pylint: disable-next=import-error,no-name-in-module
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_INTERVAL, CONF_SOLVER, CONF_STATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GasBuddyUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize."""
        self._config = config
        self.hass = hass
        self.interval = self._get_interval()
        self._data: dict[Any, Any] = {}
        self._cache_file = f"{self.hass.config.config_dir}/.storage/gasbuddy_cache"
        self._api = GasBuddy(
            solver_url=config.data[CONF_SOLVER],
            station_id=config.data[CONF_STATION_ID],
            cache_file=self._cache_file,
        )

        _LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config,
            name=DOMAIN,
            update_interval=self.interval,
        )

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        try:
            self._data = await self._api.price_lookup()
        except (APIError, LibraryError, CSRFTokenMissing) as ex:
            _LOGGER.error("Error retreiving data: %s", ex)
        except Exception as exception:
            raise UpdateFailed from exception

        self._data["last_updated"] = datetime.now(UTC)
        return self._data

    async def clear_cache(self) -> None:
        """Clear cache file."""
        await self._api.clear_cache()
        _LOGGER.debug("Cache file cleared.")

    def _get_interval(self) -> timedelta:
        """Return the update interval."""
        interval = self._config.options.get(CONF_INTERVAL)
        if interval is None:
            interval = 3600
        return timedelta(seconds=interval)
