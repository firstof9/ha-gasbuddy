"""Update coordinator for GasBuddy."""

import logging
from datetime import datetime, timedelta, timezone

from gasbuddy import GasBuddy  # pylint: disable=import-self

# pylint: disable-next=import-error,no-name-in-module
from gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .const import (
    CONF_SOLVER,
    CONF_STATION_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GasBuddyUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, interval: int, config: ConfigEntry) -> None:
        """Initialize."""
        self._config = config
        self.hass = hass
        self.interval = timedelta(seconds=interval)
        self._data = {}
        self._api = GasBuddy(
            solver_url=config.data[CONF_SOLVER], station_id=config.data[CONF_STATION_ID]
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
        except APIError:
            _LOGGER.error("API error when retreiving data.")
        except LibraryError:
            _LOGGER.error("Problem parsing API response.")
        except CSRFTokenMissing:
            _LOGGER.error("Unable to update prices due to missing token.")
        except Exception as exception:
            raise UpdateFailed() from exception

        self._data["last_updated"] = datetime.now(timezone.utc)
        return self._data
