"""Update coordinator for GasBuddy."""

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from py_gasbuddy import GasBuddy

# pylint: disable-next=import-error,no-name-in-module
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EV_CHARGING,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _redact(data: Any) -> Any:
    """Redact sensitive data for logging."""
    sensitive_keys = {
        "latitude",
        "longitude",
        "ev_access_code",
        "street_address",
        "ev_station_address",
        "city",
        "state",
        "zip",
    }
    if isinstance(data, dict):
        return {k: "**REDACTED**" if k in sensitive_keys else _redact(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_redact(item) for item in data]
    return data


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
            solver_url=config.data.get(CONF_SOLVER),
            station_id=config.data[CONF_STATION_ID],
            cache_file=self._cache_file,
            timeout=config.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            session=async_get_clientsession(hass),
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
        ev_charging_enabled = self._config.options.get(CONF_EV_CHARGING, False)
        try:
            self._data = await self._api.price_lookup()
            _LOGGER.debug("Gas station data: %s", _redact(self._data))

            config_lat = self._config.data.get("latitude")
            config_lon = self._config.data.get("longitude")
            if config_lat is not None and config_lon is not None:
                gas_lat = self._data.get("latitude")
                gas_lon = self._data.get("longitude")
                if gas_lat is not None and gas_lon is not None:
                    if abs(gas_lat - config_lat) > 1.0 or abs(gas_lon - config_lon) > 1.0:
                        raise APIError("Station ID collision detected")  # noqa: TRY301
        except (APIError, LibraryError, CSRFTokenMissing) as ex:
            if ev_charging_enabled:
                _LOGGER.warning("Price lookup failed, trying EV station fallback: %s", ex)
                try:
                    # Use coordinates from config entry if available, otherwise home coordinates
                    lat = self._config.data.get("latitude")
                    lon = self._config.data.get("longitude")
                    if lat is None:
                        lat = self.hass.config.latitude
                    if lon is None:
                        lon = self.hass.config.longitude
                    ev_res = await self._api.ev_stations_nearby(
                        lat=lat,
                        lon=lon,
                        radius=100,
                        limit=100,
                    )

                    _LOGGER.debug("EV station fallback search result: %s", _redact(ev_res))

                    matching = next(
                        (
                            s
                            for s in (ev_res or {}).get("stations", [])
                            if s.get("station_id") is not None
                            and str(s["station_id"]).strip()
                            == str(self._config.data[CONF_STATION_ID]).strip()
                        ),
                        None,
                    )
                    if matching:
                        self._data = {
                            "station_id": matching["station_id"],
                            "name": matching["name"],
                            "latitude": matching["latitude"],
                            "longitude": matching["longitude"],
                            "unit_of_measure": "dollars_per_gallon",
                            "currency": "USD",
                        }
                        # Update config entry if coordinates are new or changed
                        if (
                            self._config.data.get("latitude") != matching["latitude"]
                            or self._config.data.get("longitude") != matching["longitude"]
                        ):
                            new_data = {
                                **self._config.data,
                                "latitude": matching["latitude"],
                                "longitude": matching["longitude"],
                            }
                            self.hass.config_entries.async_update_entry(self._config, data=new_data)
                    else:
                        self._data = {
                            "station_id": self._config.data[CONF_STATION_ID],
                            "name": self._config.data.get(CONF_NAME, "EV Station"),
                            "latitude": lat,
                            "longitude": lon,
                            "unit_of_measure": "dollars_per_gallon",
                            "currency": "USD",
                        }
                except Exception as fallback_ex:  # noqa: BLE001
                    _LOGGER.error("EV fallback failed: %s", fallback_ex)
                    raise UpdateFailed(f"Error retrieving data: {ex}") from ex
            else:
                raise UpdateFailed(f"Error retrieving data: {ex}") from ex
        except Exception as exception:
            raise UpdateFailed from exception

        # Query EV station details if enabled
        if ev_charging_enabled and "latitude" in self._data and "longitude" in self._data:
            try:
                ev_res = await self._api.ev_stations_nearby(
                    lat=self._data["latitude"],
                    lon=self._data["longitude"],
                    radius=5,
                    limit=10,
                )
                _LOGGER.debug("EV station search result: %s", _redact(ev_res))
                stations = (ev_res or {}).get("stations", [])
                if stations:
                    matching = next(
                        (
                            s
                            for s in stations
                            if s.get("station_id") is not None
                            and str(s["station_id"]).strip()
                            == str(self._data["station_id"]).strip()
                        ),
                        None,
                    )
                    if matching is not None:
                        self._data["ev_level1"] = matching.get("level1_count")
                        self._data["ev_level2"] = matching.get("level2_count")
                        self._data["ev_dc_fast"] = matching.get("dc_fast_count")
                        self._data["ev_j1772"] = matching.get("j1772_count")
                        self._data["ev_j1772_power"] = matching.get("j1772_power")
                        self._data["ev_ccs"] = matching.get("ccs_count")
                        self._data["ev_ccs_power"] = matching.get("ccs_power")
                        self._data["ev_chademo"] = matching.get("chademo_count")
                        self._data["ev_chademo_power"] = matching.get("chademo_power")
                        self._data["ev_nacs"] = matching.get("nacs_count")
                        self._data["ev_nacs_power"] = matching.get("nacs_power")
                        self._data["ev_status"] = matching.get("status_code")
                        self._data["ev_network"] = matching.get("network")
                        self._data["ev_network_web"] = matching.get("network_web")
                        self._data["ev_pricing"] = matching.get("pricing")
                        self._data["ev_access_hours"] = matching.get("access_hours")
                        self._data["ev_access_code"] = matching.get("access_code")
                        self._data["ev_cards_accepted"] = matching.get("cards_accepted")
                        self._data["ev_date_last_confirmed"] = matching.get("date_last_confirmed")

                        self._data["ev_station_name"] = matching.get("name")
                        self._data["ev_station_address"] = (
                            f"{matching.get('street_address') or ''}, {matching.get('city') or ''}, {matching.get('state') or ''}"
                        )
                        self._data["ev_distance_miles"] = matching.get("distance_miles")
            except Exception as ev_ex:  # noqa: BLE001
                _LOGGER.warning("Failed to fetch EV station data: %s", ev_ex)

        self._data["last_updated"] = datetime.now(UTC)
        _LOGGER.debug("Final coordinator data: %s", _redact(self._data))
        return self._data

    async def clear_cache(self) -> None:
        """Clear cache file."""
        await self._api.clear_cache()
        _LOGGER.debug("Cache file cleared.")

    def _get_interval(self) -> timedelta:
        """Return the update interval."""
        interval = self._config.options.get(CONF_INTERVAL, 3600)
        return timedelta(seconds=interval)
