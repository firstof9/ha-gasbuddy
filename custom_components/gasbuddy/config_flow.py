"""Adds config flow for ha-gasbuddy."""

from __future__ import annotations

import logging
from typing import Any

import gasbuddy
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_STATION_ID,
    CONF_UOM,
    CONFIG_VER,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
MENU_OPTIONS = ["manual", "search"]
MENU_SEARCH = ["home", "postal"]


async def validate_station(station: int) -> bool:
    """Validate statation ID."""
    check = await gasbuddy.GasBuddy(station_id=station).price_lookup()

    if "errors" in check.keys():
        return False
    return True


async def _get_station_list(hass, user_input) -> list | None:
    """Return list of utilities by lat/lon."""
    lat = None
    lon = None
    postal = ""

    if user_input is not None and CONF_POSTAL in user_input.keys():
        postal = user_input[CONF_POSTAL]

    if not bool(postal):
        lat = hass.config.latitude
        lon = hass.config.longitude
        postal = None

    stations = await gasbuddy.GasBuddy().location_search(
        lat=lat, lon=lon, zipcode=postal
    )
    stations_list = {}
    _LOGGER.debug("search reply: %s", stations)

    for station in stations["data"]["locationBySearchTerm"]["stations"]["results"]:
        full_name = f'{station["name"]} @ {station["address"]["line1"]}'
        stations_list[station["id"]] = full_name

    if len(stations_list) == 0:
        stations_list["-"] = "No stations in search area."

    _LOGGER.debug("stations_list: %s", stations_list)
    return stations_list


# pylint: disable-next=unused-argument
def _get_schema_manual(hass: Any, user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_STATION_ID, default=_get_default(CONF_STATION_ID)): str,
            vol.Required(CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)): str,
        }
    )


def _get_schema_home(
    hass: Any,  # pylint: disable=unused-argument
    user_input: list,
    default_dict: list,
    station_list: list,
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
            vol.Required(CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)): str,
        }
    )


# pylint: disable-next=unused-argument
def _get_schema_postal(hass: Any, user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_POSTAL, default=_get_default(CONF_POSTAL)): str,
        }
    )


def _get_schema_station_list(
    hass: Any,  # pylint: disable=unused-argument
    user_input: list,
    default_dict: list,
    station_list: list,
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
            ): vol.All(vol.In(station_list), vol.NotIn(["-"])),
            vol.Required(CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)): str,
        }
    )


# pylint: disable-next=unused-argument
def _get_schema_options(hass: Any, user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any | None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_INTERVAL, default=_get_default(CONF_INTERVAL, 3600)): int,
            vol.Optional(CONF_UOM, default=_get_default(CONF_UOM)): bool,
            vol.Optional(CONF_GPS, default=_get_default(CONF_GPS)): bool,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class GasBuddyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GasBuddy."""

    VERSION = CONFIG_VER
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the flow initialized by the user."""
        return self.async_show_menu(step_id="user", menu_options=MENU_OPTIONS)

    # Manual Station ID input
    async def async_step_manual(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input[CONF_INTERVAL] = 3600
            user_input[CONF_UOM] = True
            user_input[CONF_GPS] = True
            validate = await validate_station(user_input[CONF_STATION_ID])
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
    ) -> FlowResult:
        """Handle the flow initialized by the user."""
        return self.async_show_menu(step_id="search", menu_options=MENU_SEARCH)

    # Use lat/lon from HA
    async def async_step_home(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input[CONF_INTERVAL] = 3600
            user_input[CONF_UOM] = True
            user_input[CONF_GPS] = True
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_config_home(user_input)

    async def _show_config_home(self, user_input):
        """Show the configuration form to edit location data."""
        defaults = {}

        station_list = await _get_station_list(self.hass, user_input)

        if "-" in station_list.keys():
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="home",
            data_schema=_get_schema_home(self.hass, user_input, defaults, station_list),
            errors=self._errors,
        )

    # User input postal code
    async def async_step_postal(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_station_list()
        return await self._show_config_postal(user_input)

    async def _show_config_postal(self, user_input):
        """Show the configuration form to edit location data."""
        defaults = {}

        return self.async_show_form(
            step_id="postal",
            data_schema=_get_schema_postal(self.hass, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_station_list(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            user_input[CONF_INTERVAL] = 3600
            user_input[CONF_UOM] = True
            user_input[CONF_GPS] = True
            self._data.pop(CONF_POSTAL)
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_config_station_list(user_input)

    async def _show_config_station_list(self, user_input):
        """Show the configuration form to edit location data."""
        defaults = {}

        station_list = await _get_station_list(self.hass, self._data)

        if "-" in station_list.keys():
            self._errors[CONF_STATION_ID] = "no_results"

        return self.async_show_form(
            step_id="station_list",
            data_schema=_get_schema_station_list(
                self.hass, user_input, defaults, station_list
            ),
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
        self._data = dict(config_entry.data)
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
