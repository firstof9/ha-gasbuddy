"""Update coordinator for GasBuddy."""

from datetime import UTC, datetime, timedelta
import json
import logging
import math
import operator
from typing import Any

from py_gasbuddy import GasBuddy

# pylint: disable-next=import-error,no-name-in-module
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CACHE_FILE_NAME,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_FUEL_KEY,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _lon_delta(a: float, b: float) -> float:
    """Shortest longitude delta in degrees (handles antimeridian wrap)."""
    raw = abs(a - b)
    return min(raw, 360.0 - raw)


def _redact(data: Any) -> str:
    """Redact sensitive data for logging."""
    sensitive_keys = {
        "latitude",
        "longitude",
        "street_address",
        "ev_station_address",
        "city",
        "state",
        "zip",
        "station_id",
    }

    def _redact_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "**REDACTED**" if k in sensitive_keys else _redact_recursive(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_redact_recursive(item) for item in obj]
        return obj

    try:
        return json.dumps(_redact_recursive(data), default=str)
    except (
        TypeError,
        ValueError,
    ):
        # json.dumps raises TypeError for non-serialisable objects and
        # ValueError for circular references / NaN with allow_nan=False.
        # Anything else is a real bug and should propagate.
        return str(_redact_recursive(data))


class GasBuddyUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize."""
        self._config = config
        self.hass = hass
        self.interval = self._get_interval()
        self._data: dict[Any, Any] = {}
        self._cache_file = f"{self.hass.config.config_dir}/{CACHE_FILE_NAME}"
        self._api = GasBuddy(
            solver_url=config.data.get(CONF_SOLVER),
            station_id=config.data.get(CONF_STATION_ID),
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

    async def _async_update_data(self) -> dict:  # noqa: PLR0914
        """Update data via library."""
        if self._config.data.get(CONF_CHEAPEST):
            return await self._async_update_cheapest()

        ev_charging_enabled = self._config.options.get(CONF_EV_CHARGING, False)
        fetch_gas = self._config.options.get(CONF_FETCH_GAS, True)

        if not fetch_gas:  # noqa: PLR1702
            # User has disabled gas-price polling on this station — most
            # commonly an EV-only station. Skip price_lookup entirely
            # (it would APIError every cycle) and bootstrap self._data
            # so the EV enrichment block below can populate sensors.
            if not ev_charging_enabled:
                raise UpdateFailed(
                    "Both gas price polling and EV charging are disabled — nothing to fetch."
                )
            lat = self._config.data.get("latitude") or self.hass.config.latitude
            lon = self._config.data.get("longitude") or self.hass.config.longitude
            self._data = {
                "station_id": self._config.data[CONF_STATION_ID],
                "name": self._config.data.get(CONF_NAME, "EV Station"),
                "latitude": lat,
                "longitude": lon,
            }
            _LOGGER.debug(
                "fetch_gas disabled — bootstrapping EV-only data: %s",
                _redact(self._data),
            )
        else:
            try:
                self._data = await self._api.price_lookup()
                _LOGGER.debug("Gas station data: %s", _redact(self._data))
                config_lat = self._config.data.get("latitude")
                config_lon = self._config.data.get("longitude")
                if config_lat is not None and config_lon is not None:
                    gas_lat = self._data.get("latitude")
                    gas_lon = self._data.get("longitude")
                    if gas_lat is not None and gas_lon is not None:
                        if abs(gas_lat - config_lat) > 1.0 or _lon_delta(gas_lon, config_lon) > 1.0:
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
                        # Preserve unit/currency from the last good poll where
                        # possible. Hardcoding USD/dollars_per_gallon mislabels
                        # CAD stations and any future non-USD market.
                        carried = {
                            k: v
                            for k, v in {
                                "unit_of_measure": self._data.get("unit_of_measure"),
                                "currency": self._data.get("currency"),
                            }.items()
                            if v is not None
                        }
                        if matching:
                            self._data = {
                                "station_id": matching["station_id"],
                                "name": matching["name"],
                                "latitude": matching["latitude"],
                                "longitude": matching["longitude"],
                                **carried,
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
                                self.hass.config_entries.async_update_entry(
                                    self._config, data=new_data
                                )
                        else:
                            self._data = {
                                "station_id": self._config.data[CONF_STATION_ID],
                                "name": self._config.data.get(CONF_NAME, "EV Station"),
                                "latitude": lat,
                                "longitude": lon,
                                **carried,
                            }
                    except Exception as fallback_ex:  # noqa: BLE001
                        _LOGGER.error("EV fallback failed: %s", fallback_ex)
                        raise UpdateFailed(f"Error retrieving data: {ex}") from ex
                else:
                    raise UpdateFailed(f"Error retrieving data: {ex}") from ex
            except Exception as exception:
                _LOGGER.warning("Unexpected error updating gasbuddy: %s", exception, exc_info=True)
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
                        cards = matching.get("cards_accepted")
                        if cards and isinstance(cards, str):
                            card_map = {
                                "A": "American Express",
                                "D": "Discover",
                                "Debit": "Debit Card",
                                "M": "Mastercard",
                                "V": "Visa",
                            }
                            mapped_cards = [card_map.get(c, c) for c in cards.split()]
                            self._data["ev_cards_accepted"] = ", ".join(mapped_cards)
                        else:
                            self._data["ev_cards_accepted"] = cards
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

    async def _async_update_cheapest(self) -> dict:  # noqa: PLR0914
        """Find and return the cheapest nearby station for the configured fuel and price type."""
        fuel_key = self._config.data.get(CONF_FUEL_KEY, "regular_gas")
        price_type = self._config.data.get(CONF_PRICE_TYPE, "best")

        postal = self._config.data.get(CONF_POSTAL)
        lat: float | None = None
        lon: float | None = None
        if not postal:
            config_lat = self._config.data.get("latitude")
            lat = config_lat if config_lat is not None else self.hass.config.latitude
            config_lon = self._config.data.get("longitude")
            lon = config_lon if config_lon is not None else self.hass.config.longitude

        try:
            result = await self._api.price_lookup_service(
                lat=lat,
                lon=lon,
                zipcode=postal,
                limit=20,
            )
        except (APIError, LibraryError, CSRFTokenMissing) as ex:
            raise UpdateFailed(f"Cheapest gas lookup failed: {ex}") from ex

        stations = [s for s in (result.get("results") or []) if s.get(fuel_key)]
        if not stations:
            raise UpdateFailed("No stations with prices found for selected fuel")

        exclude_brands = self._config.data.get(CONF_EXCLUDE_BRANDS) or []
        include_brands = self._config.data.get(CONF_INCLUDE_BRANDS) or []
        exclude_stations = self._config.data.get(CONF_EXCLUDE_STATIONS) or []
        include_stations = self._config.data.get(CONF_INCLUDE_STATIONS) or []

        filtered_stations = []
        for s in stations:
            station_id = str(s.get("station_id") or s.get("id") or "")
            station_brand_ids = [
                str(b.get("brandId")) for b in s.get("brands", []) if b.get("brandId")
            ]

            if exclude_stations and station_id in exclude_stations:
                continue
            if include_stations and station_id not in include_stations:
                continue
            if exclude_brands and any(b_id in exclude_brands for b_id in station_brand_ids):
                continue
            if include_brands and not any(b_id in include_brands for b_id in station_brand_ids):
                continue

            filtered_stations.append(s)

        stations = filtered_stations
        if not stations:
            raise UpdateFailed("No stations with prices found for selected fuel after filtering")

        def _sort_key(s: dict) -> float:
            node = s.get(fuel_key) or {}
            if price_type == "best":
                candidates = [node.get("deal_price"), node.get("cash_price"), node.get("price")]
                vals = [p for p in candidates if p is not None]
                return min(vals) if vals else float("inf")
            if price_type == "deal":
                dp = node.get("deal_price")
                return dp if dp is not None else float("inf")
            field = "cash_price" if price_type == "cash" else "price"
            v = node.get(field)
            return v if v is not None else float("inf")

        keyed = [(s, _sort_key(s)) for s in stations]
        finite = [(s, k) for s, k in keyed if math.isfinite(k)]
        if not finite:
            raise UpdateFailed(
                "No stations with a valid price found for selected fuel and price type"
            )
        cheapest = min(finite, key=operator.itemgetter(1))[0]
        cheapest["last_updated"] = datetime.now(UTC)
        _LOGGER.debug("Cheapest gas station: %s", _redact(cheapest))
        return cheapest

    async def clear_cache(self) -> None:
        """Clear cache file."""
        await self._api.clear_cache()
        _LOGGER.debug("Cache file cleared.")

    def _get_interval(self) -> timedelta:
        """Return the update interval."""
        interval = self._config.options.get(CONF_INTERVAL, 3600)
        return timedelta(seconds=interval)
