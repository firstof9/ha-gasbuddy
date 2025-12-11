"""Adds config flow for ha-gasbuddy."""

from __future__ import annotations

import logging
import re
from typing import Any

import py_gasbuddy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_UOM,
    CONFIG_VER,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
MENU_OPTIONS = ["manual", "search"]
MENU_SEARCH = ["home", "postal"]


async def validate_url(url: str) -> bool:
    """Validate user input URL."""
    pattern = re.compile(
        r"^(?:http|ftp)s?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(re.match(pattern, url))


async def validate_station(station: int, solver: str | None = None) -> bool:
    """Validate statation ID."""
    check = await py_gasbuddy.GasBuddy(
        solver_url=solver, station_id=station
    ).price_lookup()

    if "errors" in check:
        return False
    return True


async def _get_station_list(hass, user_input) -> dict[str, Any]:
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
        _LOGGER.debug("Using solver URL: %s", solver)

    stations = await py_gasbuddy.GasBuddy(solver_url=solver).location_search(
        lat=lat, lon=lon, zipcode=postal
    )
    stations_list = {}
    _LOGGER.debug("search reply: %s", stations)

    for station in stations["data"]["locationBySearchTerm"]["stations"]["results"]:
        full_name = f"{station['name']} @ {station['address']['line1']}"
        stations_list[station["id"]] = full_name

    if len(stations_list) == 0:
        stations_list["not_found"] = "No stations in search area."

    _LOGGER.debug("stations_list: %s", stations_list)
    return stations_list


def _get_schema_manual(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_STATION_ID, default=_get_default(CONF_STATION_ID)
            ): cv.string,
            vol.Required(
                CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
            vol.Optional(
                CONF_SOLVER, default=_get_default(CONF_SOLVER, "")
            ): cv.string,  # pylint: disable=no-value-for-parameter
        }
    )


def _get_schema_home(
    hass: Any,  # pylint: disable=unused-argument
    user_input: dict[str, Any],
    default_dict: dict[str, Any],
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_SOLVER, default=_get_default(CONF_SOLVER, "")
            ): cv.string,  # pylint: disable=no-value-for-parameter
        }
    )


def _get_schema_home2(
    hass: Any,  # pylint: disable=unused-argument
    user_input: dict[str, Any],
    default_dict: dict[str, Any],
    station_list: dict[str, Any],
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_STATION_ID, default=_get_default(CONF_STATION_ID)
            ): vol.In(station_list),
            vol.Required(
                CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
        }
    )


def _get_schema_postal(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_POSTAL, default=_get_default(CONF_POSTAL)): vol.Coerce(
                str
            ),
            vol.Optional(
                CONF_SOLVER, default=_get_default(CONF_SOLVER, "")
            ): cv.string,  # pylint: disable=no-value-for-parameter
        }
    )


def _get_schema_station_list(
    hass: Any,  # pylint: disable=unused-argument
    user_input: dict[str, Any],
    default_dict: dict[str, Any],
    station_list: dict[str, Any],
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_STATION_ID, default=_get_default(CONF_STATION_ID)
            ): vol.In(station_list),
            vol.Required(
                CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
        }
    )


def _get_schema_options(  # pylint: disable-next=unused-argument
    hass: Any, user_input: dict[str, Any], default_dict: dict[str, Any]
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_INTERVAL, default=_get_default(CONF_INTERVAL, 3600)
            ): vol.All(cv.positive_int, vol.Range(min=900, max=14400)),
            vol.Optional(CONF_UOM, default=_get_default(CONF_UOM)): cv.boolean,
            vol.Optional(CONF_GPS, default=_get_default(CONF_GPS)): cv.boolean,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class GasBuddyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GasBuddy."""

    VERSION = CONFIG_VER
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data: dict[Any, Any] = {}
        self._errors = {}
        self._entry: dict[Any, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow initialized by the user."""
        return self.async_show_menu(step_id="user", menu_options=MENU_OPTIONS)

    # Manual Station ID input
    async def async_step_manual(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input.setdefault(CONF_SOLVER)
            user_input.setdefault(CONF_INTERVAL, 3600)
            user_input.setdefault(CONF_UOM, True)
            user_input.setdefault(CONF_GPS, True)
            if user_input.get(CONF_SOLVER):
                url_valid = await validate_url(user_input[CONF_SOLVER])
                _LOGGER.debug("URL valid: %s", url_valid)
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"
                    return await self._show_config_manual(user_input)

            validate = await validate_station(
                user_input[CONF_STATION_ID], user_input[CONF_SOLVER]
            )
            if not validate:
                self._errors[CONF_STATION_ID] = "station_id"
            else:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data
                )
        return await self._show_config_manual(user_input)

    async def _show_config_manual(self, user_input):
        """Show the configuration form to edit location data."""
        # Defaults
        defaults = {
            CONF_NAME: DEFAULT_NAME,
        }

        return self.async_show_form(
            step_id="manual",
            data_schema=_get_schema_manual(self.hass, user_input, defaults),
            errors=self._errors,
        )

    # Search option
    async def async_step_search(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Handle the flow initialized by the user."""
        return self.async_show_menu(step_id="search", menu_options=MENU_SEARCH)

    # Use lat/lon from HA
    async def async_step_home(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input.setdefault(CONF_SOLVER)
            user_input.setdefault(CONF_INTERVAL, 3600)
            user_input.setdefault(CONF_UOM, True)
            user_input.setdefault(CONF_GPS, True)
            self._data.update(user_input)
            if user_input.get(CONF_SOLVER):
                url_valid = await validate_url(user_input[CONF_SOLVER])
                _LOGGER.debug("URL valid: %s", url_valid)
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"
                    return await self._show_config_home(user_input)

            return await self.async_step_home2()
        return await self._show_config_home(user_input)

    async def _show_config_home(self, user_input):
        """Show the configuration form to edit location data."""
        defaults: dict[Any, Any] = {}

        return self.async_show_form(
            step_id="home",
            data_schema=_get_schema_home(self.hass, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_home2(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input.setdefault(CONF_INTERVAL, 3600)
            user_input.setdefault(CONF_UOM, True)
            user_input.setdefault(CONF_GPS, True)
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_config_home2(user_input)

    async def _show_config_home2(self, user_input):
        """Show the configuration form to edit location data."""
        defaults: dict[Any, Any] = {}

        station_list = await _get_station_list(self.hass, self._data)

        if "not_found" in station_list:
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="home2",
            data_schema=_get_schema_home2(
                self.hass, user_input, defaults, station_list
            ),
            errors=self._errors,
        )

    # User input postal code
    async def async_step_postal(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_SOLVER):
                url_valid = await validate_url(user_input[CONF_SOLVER])
                _LOGGER.debug("URL valid: %s", url_valid)
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"
                    return await self._show_config_postal(user_input)

            return await self.async_step_station_list()
        return await self._show_config_postal(user_input)

    async def _show_config_postal(self, user_input):
        """Show the configuration form to edit location data."""
        defaults: dict[Any, Any] = {}

        return self.async_show_form(
            step_id="postal",
            data_schema=_get_schema_postal(self.hass, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_station_list(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input.setdefault(CONF_INTERVAL, 3600)
            user_input.setdefault(CONF_UOM, True)
            user_input.setdefault(CONF_GPS, True)
            self._data.pop(CONF_POSTAL)
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_config_station_list(user_input)

    async def _show_config_station_list(self, user_input):
        """Show the configuration form to edit location data."""
        defaults: dict[Any, Any] = {}

        station_list = await _get_station_list(self.hass, self._data)

        if "not_found" in station_list:
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="station_list",
            data_schema=_get_schema_station_list(
                self.hass, user_input, defaults, station_list
            ),
            errors=self._errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Add reconfigure step to allow to reconfigure a config entry."""
        entry = self._get_reconfigure_entry()
        # assert self._entry
        self._data = dict(entry.data)
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_SOLVER] != "":
                url_valid = await validate_url(user_input[CONF_SOLVER])
                _LOGGER.debug("URL valid: %s", url_valid)
                if not url_valid:
                    self._errors[CONF_SOLVER] = "invalid_url"
            else:
                user_input[CONF_SOLVER] = None

            validate = await validate_station(
                user_input[CONF_STATION_ID], user_input[CONF_SOLVER]
            )
            if not validate:
                self._errors[CONF_STATION_ID] = "station_id"

            if len(self._errors) == 0:
                self.hass.config_entries.async_update_entry(entry, data=self._data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                _LOGGER.debug("%s reconfigured.", DOMAIN)
                return self.async_abort(reason="reconfigure_successful")

            return await self._show_reconfig_form(user_input)
        return await self._show_reconfig_form(user_input)

    async def _show_reconfig_form(self, user_input):
        """Show the configuration form to edit configuration data."""
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_schema_manual(self.hass, user_input, self._data),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Enable option flow."""
        return GasBuddyOptionsFlow(config_entry)


class GasBuddyOptionsFlow(config_entries.OptionsFlow):
    """Options flow for GasBuddy."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config = config_entry
        self._data = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(self, user_input=None):
        """Manage GasBuddy options."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        """Show the configuration form to edit options."""
        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema_options(self.hass, user_input, self._data),
            errors=self._errors,
        )
