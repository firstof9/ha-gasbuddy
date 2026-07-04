"""Adds config flow for ha-gasbuddy."""

from __future__ import annotations

import logging
import re
from typing import Any

import py_gasbuddy
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError, MissingSearchData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    ObjectSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CACHE_FILE_NAME,
    CONF_BRAND_ADJUSTMENTS,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_FUEL_KEY,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SHOW_DISCOUNTED,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    FUEL_KEY_CHOICES,
    PRICE_TYPE_CHOICES,
)


def _cache_path(hass: HomeAssistant) -> str:
    """Return the shared CSRF-token cache file path."""
    return f"{hass.config.config_dir}/{CACHE_FILE_NAME}"


_LOGGER = logging.getLogger(__name__)
_STATION_ID_RE = re.compile(r"^\d{1,20}$")
_POSTAL_RE = re.compile(r"^\d{5}(-\d{4})?$|^[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d$")
MENU_OPTIONS = ["manual", "search", "cheapest"]
MENU_SEARCH = ["home", "postal"]


class InvalidStation(HomeAssistantError):
    """Error to indicate the station is invalid."""


class SearchFailed(HomeAssistantError):
    """Error to indicate the search failed."""


class CloudflareBlocked(HomeAssistantError):
    """Error to indicate the CSRF/Cloudflare check is blocking requests."""


def _csrf_blocked_via_state(gb: py_gasbuddy.GasBuddy) -> bool:
    """Return True if the just-failed call hit a CSRF/Cloudflare block.

    py_gasbuddy catches the underlying error inside its own
    ``process_request`` and surfaces a content-less ``LibraryError``,
    so the caller can't tell "Cloudflare blocked the token fetch" from
    "GasBuddy returned an error for this station ID" by inspecting the
    exception. Instead, inspect the client's post-call state. The
    ``_cf_last`` sentinel is ``None`` before any request, ``True`` after
    a request that returned parseable JSON, and ``False`` only when the
    last round-trip got a non-JSON body or a 403/non-200 status, which
    is the Cloudflare-block signature. We deliberately match ``is False``
    (not falsy) so the ``None`` initial state, the one a mocked or
    never-dispatched client reports, is not mistaken for a block.
    Private attribute, but stable across recent py_gasbuddy releases;
    once the library exposes a structured signal (see follow-up issue)
    we should switch.
    """
    return getattr(gb, "_cf_last", None) is False


def _lon_delta(a: float, b: float) -> float:
    """Return the shortest longitude delta between two points (degrees).

    Handles the antimeridian: a station at 179.9° and a server reply at
    -179.9° are 0.2° apart, not 359.8°.
    """
    raw = abs(a - b)
    return min(raw, 360.0 - raw)


def validate_url(url: str) -> bool:
    """Validate user input URL. Only http/https schemes are accepted."""
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(re.match(pattern, url))


async def validate_station(
    hass: HomeAssistant,
    station: int | str,
    solver: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any] | bool:
    """Validate station ID."""
    if str(station).strip().lower() == "hub":
        raise InvalidStation("Station ID cannot be 'hub'")

    price_error = None
    gb = py_gasbuddy.GasBuddy(
        solver_url=solver,
        station_id=station,
        cache_file=_cache_path(hass),
        session=async_get_clientsession(hass),
    )
    try:
        check = await gb.price_lookup()
        if "errors" not in check:
            gas_lat = check.get("latitude")
            gas_lon = check.get("longitude")

            # Anti-collision check: if the gas station is far from our search coordinates, it's an ID collision
            if lat is not None and lon is not None and gas_lat is not None and gas_lon is not None:
                if abs(gas_lat - lat) > 1.0 or _lon_delta(gas_lon, lon) > 1.0:
                    raise APIError("Station ID collision detected")  # noqa: TRY301

            return {
                "type": "gas",
                CONF_LATITUDE: gas_lat,
                CONF_LONGITUDE: gas_lon,
            }
    except CSRFTokenMissing as ex:
        # Forward-compat: a future py_gasbuddy release may propagate
        # this exception instead of swallowing it.
        raise CloudflareBlocked from ex
    except (APIError, LibraryError) as ex:
        # The EV path below would hit the same wall, so surface a
        # distinct error class when the cause was specifically the
        # CSRF/Cloudflare block — masking it as "Invalid station ID"
        # leaves users with no actionable diagnosis (#232).
        if _csrf_blocked_via_state(gb):
            raise CloudflareBlocked from ex
        _LOGGER.warning("Error validating station via price_lookup: %s. Trying EV check...", ex)
        price_error = ex

    try:
        ev_gb = py_gasbuddy.GasBuddy(
            solver_url=solver,
            cache_file=_cache_path(hass),
            session=async_get_clientsession(hass),
        )
        val_lat = lat if lat is not None else hass.config.latitude
        val_lon = lon if lon is not None else hass.config.longitude
        ev_res = await ev_gb.ev_stations_nearby(
            lat=val_lat,
            lon=val_lon,
            radius=100,
            limit=50,
        )
        matching = next(
            (
                s
                for s in ev_res.get("stations", [])
                if s.get("station_id") is not None
                and str(s["station_id"]).strip() == str(station).strip()
            ),
            None,
        )
        if matching:
            return {
                "type": "ev",
                CONF_LATITUDE: matching.get("latitude"),
                CONF_LONGITUDE: matching.get("longitude"),
            }
    except Exception as ev_ex:
        if _csrf_blocked_via_state(ev_gb):
            raise CloudflareBlocked from ev_ex
        _LOGGER.warning("Error validating EV station: %s", ev_ex)

    if price_error is not None:
        raise InvalidStation from price_error

    return False


async def _get_station_list(  # noqa: PLR0914
    hass: HomeAssistant, user_input, flow_id: str | None = None
) -> dict[str, Any]:
    """Return list of utilities by lat/lon."""
    lat = None
    lon = None
    postal: str | None = ""
    solver = None

    if user_input is not None and CONF_POSTAL in user_input:
        postal = user_input[CONF_POSTAL]

    if not bool(postal):
        lat = hass.config.latitude
        lon = hass.config.longitude
        postal = None

    if user_input is not None and CONF_SOLVER in user_input and user_input[CONF_SOLVER]:
        solver = user_input[CONF_SOLVER]
        _LOGGER.debug("Solver URL configured: %s", bool(solver))

    try:
        stations = await py_gasbuddy.GasBuddy(
            solver_url=solver,
            cache_file=_cache_path(hass),
            session=async_get_clientsession(hass),
        ).location_search(lat=lat, lon=lon, zipcode=postal)
    except MissingSearchData as ex:
        _LOGGER.warning("Error searching for stations: %s", ex)
        raise SearchFailed from ex

    stations_list = {}
    _LOGGER.debug("search reply: %s stations returned", len(stations.get("results", [])))

    for station in stations.get("results", []):
        station_id = station.get("station_id")
        if station_id is None:
            continue
        addr = (station.get("address") or {}).get("line1", "")
        full_name = f"{station.get('name', 'Unknown')} @ {addr}"
        stations_list[station_id] = full_name

    # Query EV stations nearby and merge them
    search_lat = lat
    search_lon = lon

    if search_lat is None and postal is not None:
        try:
            res = await py_gasbuddy.GasBuddy(
                solver_url=solver,
                cache_file=_cache_path(hass),
                session=async_get_clientsession(hass),
            ).price_lookup_service(zipcode=postal)
            if res.get("results"):
                search_lat = res["results"][0].get("latitude")
                search_lon = res["results"][0].get("longitude")
        except Exception as ex:  # noqa: BLE001
            _LOGGER.debug(
                "Could not resolve postal code to coordinates via price_lookup_service: %s", ex
            )

    if search_lat is not None and search_lon is not None:
        try:
            ev_gb = py_gasbuddy.GasBuddy(
                solver_url=solver,
                cache_file=_cache_path(hass),
                session=async_get_clientsession(hass),
            )
            ev_res = await ev_gb.ev_stations_nearby(
                lat=search_lat,
                lon=search_lon,
                radius=10,
                limit=20,
            )
            for ev_station in ev_res.get("stations", []):
                ev_id = ev_station["station_id"]
                full_name = f"{ev_station['name']} @ {ev_station.get('street_address') or ''} [EV]"
                stations_list[ev_id] = full_name
                # Cache coordinates (bounded to 50 flow IDs)
                hass.data.setdefault(DOMAIN, {})
                coord_cache = hass.data[DOMAIN].setdefault("station_coordinates_by_flow", {})
                if len(coord_cache) >= 50:
                    for old_key in list(coord_cache.keys())[:10]:
                        coord_cache.pop(old_key, None)
                flow_cache = coord_cache.setdefault(flow_id, {})
                flow_cache[str(ev_id)] = (
                    ev_station.get("latitude"),
                    ev_station.get("longitude"),
                )
        except Exception as ev_ex:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch EV stations for search: %s", ev_ex)

    if len(stations_list) == 0:
        stations_list["not_found"] = "No stations in search area."

    _LOGGER.debug("stations_list: %s", stations_list)
    return stations_list


async def _get_nearby_brands_and_stations(
    hass: HomeAssistant,
    postal: str | None,
    solver: str | None,
    timeout: int,
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch nearby stations and return unique brands and stations dicts."""
    lat = None
    lon = None
    if not postal:
        lat = hass.config.latitude
        lon = hass.config.longitude

    gb = py_gasbuddy.GasBuddy(
        solver_url=solver,
        cache_file=_cache_path(hass),
        timeout=timeout,
        session=async_get_clientsession(hass),
    )
    try:
        result = await gb.price_lookup_service(lat=lat, lon=lon, zipcode=postal, limit=20)
    except CSRFTokenMissing as ex:
        raise CloudflareBlocked from ex
    except (APIError, LibraryError) as ex:
        if _csrf_blocked_via_state(gb):
            raise CloudflareBlocked from ex
        _LOGGER.warning("Error fetching nearby stations for filtering: %s", ex)
        return {}, {}
    except Exception as ex:  # noqa: BLE001
        _LOGGER.warning("Unexpected error fetching nearby stations for filtering: %s", ex)
        return {}, {}

    brands = {}
    stations = {}
    for station in result.get("results") or []:
        station_id = station.get("station_id") or station.get("id")
        if not station_id:
            continue
        station_id = str(station_id)
        addr = (station.get("address") or {}).get("line1", "")
        name = station.get("name", "Unknown")
        stations[station_id] = f"{name} ({addr})" if addr else name

        for brand in station.get("brands", []):
            brand_id = brand.get("brandId")
            brand_name = brand.get("name")
            if brand_id and brand_name:
                brands[str(brand_id)] = str(brand_name)

    return brands, stations


# ── Schema helpers ──────────────────────────────────────────────────────────


def _get_schema_manual(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema({
        vol.Required(CONF_STATION_ID, default=_get_default(CONF_STATION_ID)): vol.All(
            cv.string, vol.Strip
        ),
        vol.Required(CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)): vol.All(
            cv.string, vol.Strip, vol.Length(max=100)
        ),
        vol.Required(CONF_INTERVAL, default=_get_default(CONF_INTERVAL, 3600)): vol.All(
            cv.positive_int, vol.Range(min=900, max=14400)
        ),
        vol.Optional(CONF_UOM, default=_get_default(CONF_UOM, True)): cv.boolean,
        vol.Optional(CONF_GPS, default=_get_default(CONF_GPS, True)): cv.boolean,
        vol.Optional(CONF_EV_CHARGING, default=_get_default(CONF_EV_CHARGING, False)): cv.boolean,
        vol.Optional(CONF_FETCH_GAS, default=_get_default(CONF_FETCH_GAS, True)): cv.boolean,
        vol.Optional(
            CONF_SHOW_DISCOUNTED, default=_get_default(CONF_SHOW_DISCOUNTED, False)
        ): cv.boolean,
    })


def _get_schema_station_list(
    hass: Any,  # pylint: disable=unused-argument
    user_input: dict[str, Any] | None,
    default_dict: dict[str, Any],
    station_list: dict[str, Any],
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema({
        vol.Required(CONF_STATION_ID, default=_get_default(CONF_STATION_ID)): vol.In(station_list),
        vol.Required(CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)): vol.All(
            cv.string, vol.Strip, vol.Length(max=100)
        ),
    })


def _get_schema_cheapest(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema for the cheapest gas tracker setup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema({
        vol.Required(CONF_NAME, default=_get_default(CONF_NAME, "Cheapest Gas")): vol.All(
            cv.string, vol.Strip, vol.Length(max=100)
        ),
        vol.Optional(CONF_POSTAL, default=_get_default(CONF_POSTAL, "")): vol.All(
            vol.Coerce(str), vol.Strip
        ),
        vol.Required(
            CONF_FUEL_KEY, default=_get_default(CONF_FUEL_KEY, "regular_gas")
        ): SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=v) for k, v in FUEL_KEY_CHOICES.items()],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_PRICE_TYPE, default=_get_default(CONF_PRICE_TYPE, "best")
        ): SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=v) for k, v in PRICE_TYPE_CHOICES.items()],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    })


def _get_schema_cheapest_filters(
    hass: Any,
    brands: dict[str, str],
    stations: dict[str, str],
    user_input: dict[str, Any] | None,
    default_dict: dict[str, Any],
) -> Any:
    """Get a schema for Cheapest Gas brand and station filters."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    brand_options = [SelectOptionDict(value=k, label=v) for k, v in brands.items()]
    station_options = [SelectOptionDict(value=k, label=v) for k, v in stations.items()]

    return vol.Schema({
        vol.Optional(
            CONF_EXCLUDE_BRANDS, default=_get_default(CONF_EXCLUDE_BRANDS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=brand_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_INCLUDE_BRANDS, default=_get_default(CONF_INCLUDE_BRANDS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=brand_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_EXCLUDE_STATIONS, default=_get_default(CONF_EXCLUDE_STATIONS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=station_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_INCLUDE_STATIONS, default=_get_default(CONF_INCLUDE_STATIONS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=station_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    })


def _get_schema_options(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema({
        vol.Required(CONF_INTERVAL, default=_get_default(CONF_INTERVAL, 3600)): vol.All(
            cv.positive_int, vol.Range(min=900, max=14400)
        ),
        vol.Optional(CONF_UOM, default=_get_default(CONF_UOM)): cv.boolean,
        vol.Optional(CONF_GPS, default=_get_default(CONF_GPS)): cv.boolean,
        vol.Optional(CONF_EV_CHARGING, default=_get_default(CONF_EV_CHARGING, False)): cv.boolean,
        vol.Optional(CONF_FETCH_GAS, default=_get_default(CONF_FETCH_GAS, True)): cv.boolean,
        vol.Optional(
            CONF_SHOW_DISCOUNTED, default=_get_default(CONF_SHOW_DISCOUNTED, False)
        ): cv.boolean,
    })


# ── Main Config Flow (Hub only) ────────────────────────────────────────────


@config_entries.HANDLERS.register(DOMAIN)
class GasBuddyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GasBuddy."""

    VERSION = CONFIG_VER

    def __init__(self):
        """Initialize."""
        self._data: dict[Any, Any] = {}
        self._errors = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the flow initialized by the user — creates the hub entry."""
        # Only one hub allowed
        await self.async_set_unique_id("hub")
        self._abort_if_unique_id_configured()

        self._errors = {}

        if user_input is not None:
            user_input.setdefault(CONF_NAME, "GasBuddy Hub")
            user_input.setdefault(CONF_SOLVER, "")
            user_input.setdefault(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            user_input.setdefault(CONF_BRAND_ADJUSTMENTS, {})
            if user_input.get(CONF_SOLVER):
                url_valid = validate_url(user_input[CONF_SOLVER])
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"

            if not self._errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        defaults = {
            CONF_NAME: "GasBuddy Hub",
            CONF_SOLVER: "",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_BRAND_ADJUSTMENTS: {},
        }
        if user_input:
            defaults.update(user_input)

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=defaults[CONF_NAME]): vol.All(
                cv.string, vol.Strip, vol.Length(max=100)
            ),
            vol.Optional(CONF_SOLVER, default=defaults[CONF_SOLVER]): vol.All(cv.string, vol.Strip),
            vol.Optional(CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]): vol.All(
                cv.positive_int, vol.Range(min=1000, max=300000)
            ),
            vol.Optional(
                CONF_BRAND_ADJUSTMENTS, default=defaults[CONF_BRAND_ADJUSTMENTS]
            ): ObjectSelector(),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"station": GasBuddySubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Enable option flow."""
        return GasBuddyOptionsFlow()


# ── Subentry Flow (Station management) ─────────────────────────────────────


class GasBuddySubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing GasBuddy station subentries."""

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self._station_list: dict[str, Any] = {}

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Show station type menu when adding a new subentry."""
        return self.async_show_menu(step_id="user", menu_options=MENU_OPTIONS)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a station subentry."""
        subentry = self._get_reconfigure_subentry()
        self._data = dict(subentry.data)
        self._errors = {}

        if self._data.get(CONF_CHEAPEST):
            return await self.async_step_reconfigure_cheapest(user_input)

        if user_input is not None:
            self._data.update(user_input)
            station_id = str(user_input.get(CONF_STATION_ID, "")).strip()
            if not _STATION_ID_RE.match(station_id):
                self._errors[CONF_STATION_ID] = "station_id"
                return await self._show_reconfig_form(user_input)

            try:
                validate = await validate_station(
                    self.hass,
                    user_input[CONF_STATION_ID],
                    self._get_entry().data.get(CONF_SOLVER),
                )
            except CloudflareBlocked:
                self._errors[CONF_STATION_ID] = "cloudflare"
                validate = False
            except InvalidStation:
                validate = False

            if not validate:
                self._errors.setdefault(CONF_STATION_ID, "station_id")

            if len(self._errors) == 0:
                if str(subentry.data.get(CONF_STATION_ID)) != station_id:
                    if isinstance(validate, dict):
                        self._data[CONF_LATITUDE] = validate.get(CONF_LATITUDE)
                        self._data[CONF_LONGITUDE] = validate.get(CONF_LONGITUDE)
                        self._data[CONF_EV_CHARGING] = validate["type"] == "ev"
                        self._data[CONF_FETCH_GAS] = validate["type"] != "ev"
                    else:
                        self._data[CONF_EV_CHARGING] = False
                        self._data[CONF_FETCH_GAS] = True
                elif isinstance(validate, dict):
                    self._data[CONF_LATITUDE] = validate.get(CONF_LATITUDE)
                    self._data[CONF_LONGITUDE] = validate.get(CONF_LONGITUDE)

                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=self._data,
                    title=self._data.get(CONF_NAME, subentry.title),
                    unique_id=str(self._data[CONF_STATION_ID]),
                )

            return await self._show_reconfig_form(user_input)
        return await self._show_reconfig_form(user_input)

    async def _show_reconfig_form(self, user_input) -> SubentryFlowResult:
        """Show the configuration form to edit configuration data."""
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_schema_manual(self.hass, user_input, self._data),
            errors=self._errors,
        )

    # ── Manual station ─────────────────────────────────────────────────

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle manual station ID input."""
        self._errors = {}

        if user_input is not None:
            station_id = str(user_input.get(CONF_STATION_ID, "")).strip()
            if not _STATION_ID_RE.match(station_id):
                self._errors[CONF_STATION_ID] = "station_id"
                return await self._show_config_manual(user_input)

            try:
                validate = await validate_station(
                    self.hass,
                    user_input[CONF_STATION_ID],
                    self._get_entry().data.get(CONF_SOLVER),
                )
            except CloudflareBlocked:
                self._errors[CONF_STATION_ID] = "cloudflare"
                validate = False
            except InvalidStation:
                validate = False

            if not validate:
                self._errors.setdefault(CONF_STATION_ID, "station_id")
            else:
                self._data.update(user_input)
                if isinstance(validate, dict):
                    self._data[CONF_LATITUDE] = validate.get(CONF_LATITUDE)
                    self._data[CONF_LONGITUDE] = validate.get(CONF_LONGITUDE)
                    if validate["type"] == "ev":
                        self._data[CONF_EV_CHARGING] = True
                        self._data[CONF_FETCH_GAS] = False
                    else:
                        self._data[CONF_EV_CHARGING] = self._data.get(CONF_EV_CHARGING, False)
                        self._data[CONF_FETCH_GAS] = self._data.get(CONF_FETCH_GAS, True)
                else:
                    self._data[CONF_EV_CHARGING] = self._data.get(CONF_EV_CHARGING, False)
                    self._data[CONF_FETCH_GAS] = self._data.get(CONF_FETCH_GAS, True)

                subentry_data = {
                    CONF_STATION_ID: self._data[CONF_STATION_ID],
                    CONF_NAME: self._data.get(CONF_NAME, DEFAULT_NAME),
                    CONF_LATITUDE: self._data.get(CONF_LATITUDE),
                    CONF_LONGITUDE: self._data.get(CONF_LONGITUDE),
                    CONF_INTERVAL: self._data.get(CONF_INTERVAL, 3600),
                    CONF_UOM: self._data.get(CONF_UOM, True),
                    CONF_GPS: self._data.get(CONF_GPS, True),
                    CONF_EV_CHARGING: self._data[CONF_EV_CHARGING],
                    CONF_FETCH_GAS: self._data[CONF_FETCH_GAS],
                    CONF_SHOW_DISCOUNTED: self._data.get(CONF_SHOW_DISCOUNTED, False),
                }
                return self.async_create_entry(
                    title=subentry_data[CONF_NAME],
                    data=subentry_data,
                    unique_id=str(subentry_data[CONF_STATION_ID]),
                )
        return await self._show_config_manual(user_input)

    async def _show_config_manual(self, user_input) -> SubentryFlowResult:
        """Show the configuration form to edit location data."""
        defaults = {
            CONF_NAME: DEFAULT_NAME,
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_GPS: True,
            CONF_EV_CHARGING: False,
            CONF_FETCH_GAS: True,
            CONF_SHOW_DISCOUNTED: False,
        }
        return self.async_show_form(
            step_id="manual",
            data_schema=_get_schema_manual(self.hass, user_input, defaults),
            errors=self._errors,
        )

    # ── Search menu ────────────────────────────────────────────────────

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the search sub-menu."""
        return self.async_show_menu(step_id="search", menu_options=MENU_SEARCH)

    # ── Search by home coordinates ─────────────────────────────────────

    async def async_step_home(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Handle search by home coordinates."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_home2()
        return self.async_show_form(step_id="home", data_schema=vol.Schema({}))

    async def async_step_home2(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle station selection from home search results."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self._async_validate_and_create_subentry()
        return await self._show_config_home2(user_input)

    async def _show_config_home2(self, user_input) -> SubentryFlowResult:
        """Show the station list from home search."""
        defaults: dict[Any, Any] = {}

        try:
            station_list = await _get_station_list(self.hass, self._data, self.flow_id)
            self._station_list = station_list
        except SearchFailed:
            station_list = {"not_found": "Error searching for stations."}

        if "not_found" in station_list:
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="home2",
            data_schema=_get_schema_station_list(self.hass, user_input, defaults, station_list),
            errors=self._errors,
        )

    # ── Search by postal code ──────────────────────────────────────────

    async def async_step_postal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle postal code search."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            postal = str(user_input.get(CONF_POSTAL, "")).strip()
            if not _POSTAL_RE.match(postal):
                self._errors[CONF_POSTAL] = "invalid_postal"
                return await self._show_config_postal(user_input)
            return await self.async_step_station_list()
        return await self._show_config_postal(user_input)

    async def _show_config_postal(self, user_input) -> SubentryFlowResult:
        """Show the postal code input form."""
        return self.async_show_form(
            step_id="postal",
            data_schema=vol.Schema({
                vol.Required(CONF_POSTAL): vol.All(vol.Coerce(str), vol.Strip),
            }),
            errors=self._errors,
        )

    async def async_step_station_list(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle station selection from postal search results."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self._async_validate_and_create_subentry()
        return await self._show_config_station_list(user_input)

    async def _show_config_station_list(self, user_input) -> SubentryFlowResult:
        """Show the station list from postal search."""
        defaults: dict[Any, Any] = {}

        try:
            station_list = await _get_station_list(self.hass, self._data, self.flow_id)
            self._station_list = station_list
        except SearchFailed:
            station_list = {"not_found": "Error searching for stations."}

        if "not_found" in station_list:
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="station_list",
            data_schema=_get_schema_station_list(self.hass, user_input, defaults, station_list),
            errors=self._errors,
        )

    # ── Cheapest gas ───────────────────────────────────────────────────

    async def async_step_cheapest(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the cheapest gas tracker flow (Step 1)."""
        self._errors = {}

        if user_input is not None:
            data: dict[str, Any] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_CHEAPEST: True,
                CONF_FUEL_KEY: user_input[CONF_FUEL_KEY],
                CONF_PRICE_TYPE: user_input[CONF_PRICE_TYPE],
            }
            postal = (user_input.get(CONF_POSTAL) or "").strip()
            if postal:
                if not _POSTAL_RE.match(postal):
                    self._errors[CONF_POSTAL] = "invalid_postal"
                    return await self._show_config_cheapest(user_input)
                data[CONF_POSTAL] = postal

            self._data.update(data)
            return await self.async_step_cheapest_filters()
        return await self._show_config_cheapest(user_input)

    async def async_step_cheapest_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle Step 2: Brand/station filters for cheapest gas tracker."""
        self._errors = {}

        if user_input is not None:
            subentry_data: dict[str, Any] = {
                CONF_NAME: self._data[CONF_NAME],
                CONF_CHEAPEST: True,
                CONF_FUEL_KEY: self._data[CONF_FUEL_KEY],
                CONF_PRICE_TYPE: self._data[CONF_PRICE_TYPE],
                CONF_EXCLUDE_BRANDS: user_input.get(CONF_EXCLUDE_BRANDS, []),
                CONF_INCLUDE_BRANDS: user_input.get(CONF_INCLUDE_BRANDS, []),
                CONF_EXCLUDE_STATIONS: user_input.get(CONF_EXCLUDE_STATIONS, []),
                CONF_INCLUDE_STATIONS: user_input.get(CONF_INCLUDE_STATIONS, []),
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_GPS: False,
                CONF_EV_CHARGING: False,
                CONF_FETCH_GAS: True,
            }
            if CONF_POSTAL in self._data:
                subentry_data[CONF_POSTAL] = self._data[CONF_POSTAL]

            return self.async_create_entry(
                title=subentry_data[CONF_NAME],
                data=subentry_data,
            )

        entry = self._get_entry()
        solver = entry.data.get(CONF_SOLVER)
        timeout = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        try:
            brands, stations = await _get_nearby_brands_and_stations(
                self.hass,
                self._data.get(CONF_POSTAL),
                solver,
                timeout,
            )
        except CloudflareBlocked:
            self._errors[CONF_SOLVER] = "cloudflare"
            return await self._show_config_cheapest(self._data)

        return self.async_show_form(
            step_id="cheapest_filters",
            data_schema=_get_schema_cheapest_filters(
                self.hass, brands, stations, user_input, self._data
            ),
            description_placeholders={
                "brand_adjustments_url": "https://github.com/firstof9/ha-gasbuddy#brand-price-adjustments"
            },
            errors=self._errors,
        )

    async def _show_config_cheapest(self, user_input) -> SubentryFlowResult:
        """Show the cheapest gas tracker configuration form."""
        return self.async_show_form(
            step_id="cheapest",
            data_schema=_get_schema_cheapest(self.hass, user_input, {}),
            errors=self._errors,
        )

    # ── Cheapest reconfigure ───────────────────────────────────────────

    async def async_step_reconfigure_cheapest(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfigure for a cheapest gas tracker subentry (Step 1)."""
        if user_input is not None:
            new_data: dict[str, Any] = {
                **self._data,
                CONF_NAME: user_input[CONF_NAME],
                CONF_FUEL_KEY: user_input[CONF_FUEL_KEY],
                CONF_PRICE_TYPE: user_input[CONF_PRICE_TYPE],
            }
            postal = (user_input.get(CONF_POSTAL) or "").strip()
            if postal:
                if not _POSTAL_RE.match(postal):
                    self._errors[CONF_POSTAL] = "invalid_postal"
                    return await self._show_reconfig_cheapest_form(user_input)
                new_data[CONF_POSTAL] = postal
            else:
                new_data.pop(CONF_POSTAL, None)

            self._data = new_data
            return await self.async_step_reconfigure_cheapest_filters()

        return await self._show_reconfig_cheapest_form(user_input)

    async def async_step_reconfigure_cheapest_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle Step 2 filters for cheapest gas tracker reconfiguration."""
        self._errors = {}

        if user_input is not None:
            new_data: dict[str, Any] = {
                **self._data,
                CONF_EXCLUDE_BRANDS: user_input.get(CONF_EXCLUDE_BRANDS, []),
                CONF_INCLUDE_BRANDS: user_input.get(CONF_INCLUDE_BRANDS, []),
                CONF_EXCLUDE_STATIONS: user_input.get(CONF_EXCLUDE_STATIONS, []),
                CONF_INCLUDE_STATIONS: user_input.get(CONF_INCLUDE_STATIONS, []),
            }

            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=new_data,
                title=new_data[CONF_NAME],
            )

        entry = self._get_entry()
        solver = entry.data.get(CONF_SOLVER)
        timeout = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        try:
            brands, stations = await _get_nearby_brands_and_stations(
                self.hass,
                self._data.get(CONF_POSTAL),
                solver,
                timeout,
            )
        except CloudflareBlocked:
            self._errors[CONF_SOLVER] = "cloudflare"
            return await self._show_reconfig_cheapest_form(self._data)

        return self.async_show_form(
            step_id="reconfigure_cheapest_filters",
            data_schema=_get_schema_cheapest_filters(
                self.hass, brands, stations, user_input, self._data
            ),
            description_placeholders={
                "brand_adjustments_url": "https://github.com/firstof9/ha-gasbuddy#brand-price-adjustments"
            },
            errors=self._errors,
        )

    async def _show_reconfig_cheapest_form(self, user_input) -> SubentryFlowResult:
        """Show the cheapest reconfigure form pre-filled with current subentry data."""
        return self.async_show_form(
            step_id="reconfigure_cheapest",
            data_schema=_get_schema_cheapest(self.hass, user_input, self._data),
            errors=self._errors,
        )

    # ── Shared helper ──────────────────────────────────────────────────

    async def _async_validate_and_create_subentry(self) -> SubentryFlowResult:
        """Validate selected station and create subentry."""
        flow_cache = (
            self.hass.data
            .get(DOMAIN, {})
            .get("station_coordinates_by_flow", {})
            .pop(self.flow_id, {})
        )
        cached_coords = flow_cache.get(str(self._data[CONF_STATION_ID]))
        lat, lon = cached_coords or (None, None)

        try:
            validate = await validate_station(
                self.hass,
                self._data[CONF_STATION_ID],
                self._get_entry().data.get(CONF_SOLVER),
                lat=lat,
                lon=lon,
            )
        except CloudflareBlocked:
            self._errors[CONF_STATION_ID] = "cloudflare"
            validate = False
        except InvalidStation:
            validate = False

        if not validate:
            self._errors.setdefault(CONF_STATION_ID, "station_id")
            # Return to the last shown form
            if self._station_list:
                return self.async_show_form(
                    step_id="home2" if CONF_POSTAL not in self._data else "station_list",
                    data_schema=_get_schema_station_list(self.hass, None, {}, self._station_list),
                    errors=self._errors,
                )
            return await self._show_config_manual(None)

        if isinstance(validate, dict):
            self._data[CONF_LATITUDE] = validate.get(CONF_LATITUDE)
            self._data[CONF_LONGITUDE] = validate.get(CONF_LONGITUDE)
            ev_charging = validate["type"] == "ev"
        else:
            ev_charging = False

        subentry_data = {
            CONF_STATION_ID: self._data[CONF_STATION_ID],
            CONF_NAME: self._data.get(CONF_NAME, DEFAULT_NAME),
            CONF_LATITUDE: self._data.get(CONF_LATITUDE),
            CONF_LONGITUDE: self._data.get(CONF_LONGITUDE),
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_GPS: True,
            CONF_EV_CHARGING: ev_charging,
            CONF_FETCH_GAS: not ev_charging,
        }
        return self.async_create_entry(
            title=subentry_data[CONF_NAME],
            data=subentry_data,
            unique_id=str(subentry_data[CONF_STATION_ID]),
        )


# ── Options Flow (Hub settings) ────────────────────────────────────────────


class GasBuddyOptionsFlow(config_entries.OptionsFlow):
    """Options flow for GasBuddy Hub."""

    def __init__(self) -> None:
        """Initialize.

        HA 2024.12+ provides ``self.config_entry`` automatically on the
        base class — taking ``config_entry`` here triggers a deprecation
        warning. The previous ``self.config = config_entry`` field was
        never read.
        """
        self._data: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    async def async_step_init(self, user_input=None):
        """Manage GasBuddy Hub options."""
        if not self._data:
            self._data = {
                CONF_NAME: self.config_entry.data.get(CONF_NAME, "GasBuddy Hub"),
                CONF_SOLVER: self.config_entry.data.get(CONF_SOLVER, ""),
                CONF_TIMEOUT: self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                CONF_BRAND_ADJUSTMENTS: self.config_entry.data.get(CONF_BRAND_ADJUSTMENTS, {}),
            }
        self._errors = {}
        if user_input is not None:
            user_input.setdefault(CONF_NAME, "GasBuddy Hub")
            user_input.setdefault(CONF_SOLVER, "")
            user_input.setdefault(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            user_input.setdefault(CONF_BRAND_ADJUSTMENTS, {})
            if user_input.get(CONF_SOLVER):
                url_valid = validate_url(user_input[CONF_SOLVER])
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"

            if not self._errors:
                self._data.update(user_input)
                # Store hub settings in entry.data (not options)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=self._data[CONF_NAME],
                    data={
                        **self.config_entry.data,
                        **self._data,
                    },
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=self._data[CONF_NAME]): vol.All(
                cv.string, vol.Strip, vol.Length(max=100)
            ),
            vol.Optional(CONF_SOLVER, default=self._data[CONF_SOLVER]): vol.All(
                cv.string, vol.Strip
            ),
            vol.Optional(CONF_TIMEOUT, default=self._data[CONF_TIMEOUT]): vol.All(
                cv.positive_int, vol.Range(min=1000, max=300000)
            ),
            vol.Optional(
                CONF_BRAND_ADJUSTMENTS, default=self._data[CONF_BRAND_ADJUSTMENTS]
            ): ObjectSelector(),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "brand_adjustments_url": "https://github.com/firstof9/ha-gasbuddy#brand-price-adjustments"
            },
            errors=self._errors,
        )
