"""GasBuddy services."""

import logging

from py_gasbuddy import GasBuddy
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, LibraryError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_DEVICE_ID,
    ATTR_LIMIT,
    ATTR_POSTAL_CODE,
    ATTR_RADIUS,
    ATTR_SOLVER,
    CACHE_FILE_NAME,
    COORDINATOR,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_EV_LOOKUP_GPS,
    SERVICE_EV_LOOKUP_ZIP,
    SERVICE_LOOKUP_GPS,
    SERVICE_LOOKUP_ZIP,
)

_LOGGER = logging.getLogger(__name__)


def _cache_path(hass: HomeAssistant) -> str:
    """Return the shared CSRF-token cache file path."""
    return f"{hass.config.config_dir}/{CACHE_FILE_NAME}"


class GasBuddyServices:
    """Class that holds our services."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
    ) -> None:
        """Initialize with hass object."""
        self.hass = hass
        self._config = config

    @callback
    def async_register(self) -> None:
        """Register all our services."""
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            self._price_lookup_gps,
            schema=vol.Schema({
                vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                vol.Optional(ATTR_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                vol.Optional(ATTR_SOLVER): cv.string,
            }),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            self._price_lookup_zip,
            schema=vol.Schema({
                vol.Required(ATTR_POSTAL_CODE): cv.string,
                vol.Optional(ATTR_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                vol.Optional(ATTR_SOLVER): cv.string,
            }),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_EV_LOOKUP_GPS,
            self._ev_lookup_gps,
            schema=vol.Schema({
                vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                vol.Optional(ATTR_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                vol.Optional(ATTR_RADIUS): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Optional(ATTR_SOLVER): cv.string,
            }),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_EV_LOOKUP_ZIP,
            self._ev_lookup_zip,
            schema=vol.Schema({
                vol.Required(ATTR_POSTAL_CODE): cv.string,
                vol.Optional(ATTR_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                vol.Optional(ATTR_RADIUS): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Optional(ATTR_SOLVER): cv.string,
            }),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            self._clear_cache,
            schema=vol.Schema({
                vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            }),
        )

    @callback
    def async_unregister(self) -> None:
        """Unregister all our services."""
        self.hass.services.async_remove(DOMAIN, SERVICE_LOOKUP_GPS)
        self.hass.services.async_remove(DOMAIN, SERVICE_LOOKUP_ZIP)
        self.hass.services.async_remove(DOMAIN, SERVICE_EV_LOOKUP_GPS)
        self.hass.services.async_remove(DOMAIN, SERVICE_EV_LOOKUP_ZIP)
        self.hass.services.async_remove(DOMAIN, SERVICE_CLEAR_CACHE)

    # Setup services
    async def _price_lookup_gps(self, service: ServiceCall) -> ServiceResponse:
        """Lookup prices with GPS coordinates."""
        entity_ids = service.data[ATTR_ENTITY_ID]

        limit = 5
        solver = None

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]

        if ATTR_SOLVER in service.data:
            solver = service.data[ATTR_SOLVER]

        results = {}
        api = GasBuddy(
            solver_url=solver,
            cache_file=_cache_path(self.hass),
            session=async_get_clientsession(self.hass),
        )
        for entity_id in entity_ids:
            try:
                entity = self.hass.states.get(entity_id)
                if entity:
                    lat = entity.attributes[ATTR_LATITUDE]
                    lon = entity.attributes[ATTR_LONGITUDE]
                    results[entity_id] = await api.price_lookup_service(
                        lat=lat, lon=lon, limit=limit
                    )
            except (APIError, LibraryError, CSRFTokenMissing) as ex:
                _LOGGER.error("Error checking prices: %s", ex)

        _LOGGER.debug("GPS price lookup: %s", results)
        return results

    async def _price_lookup_zip(self, service: ServiceCall) -> ServiceResponse:
        """Lookup prices via ZIP code."""
        zipcode = service.data[ATTR_POSTAL_CODE]

        limit = 5
        solver = None

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]
        if ATTR_SOLVER in service.data:
            solver = service.data[ATTR_SOLVER]

        results = {}
        try:
            results = await GasBuddy(
                solver_url=solver,
                cache_file=_cache_path(self.hass),
                session=async_get_clientsession(self.hass),
            ).price_lookup_service(zipcode=zipcode, limit=limit)
        except (APIError, LibraryError, CSRFTokenMissing) as ex:
            _LOGGER.error("Error checking prices: %s", ex)

        _LOGGER.debug("ZIP Code price lookup: %s", results)
        return results

    async def _ev_lookup_gps(self, service: ServiceCall) -> ServiceResponse:
        """Lookup EV stations with GPS coordinates."""
        entity_ids = service.data[ATTR_ENTITY_ID]

        limit = 5
        radius = 25
        solver = None

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]
        if ATTR_RADIUS in service.data:
            radius = service.data[ATTR_RADIUS]
        if ATTR_SOLVER in service.data:
            solver = service.data[ATTR_SOLVER]

        results = {}
        api = GasBuddy(
            solver_url=solver,
            cache_file=_cache_path(self.hass),
            session=async_get_clientsession(self.hass),
        )
        for entity_id in entity_ids:
            try:
                entity = self.hass.states.get(entity_id)
                if (
                    entity
                    and ATTR_LATITUDE in entity.attributes
                    and ATTR_LONGITUDE in entity.attributes
                ):
                    lat = entity.attributes[ATTR_LATITUDE]
                    lon = entity.attributes[ATTR_LONGITUDE]
                    res = await api.ev_stations_nearby(lat=lat, lon=lon, radius=radius, limit=limit)
                    results[entity_id] = res.get("stations", [])
                else:
                    _LOGGER.warning("Entity %s lacks latitude/longitude coordinates", entity_id)
                    results[entity_id] = []
            except Exception as ex:  # noqa: BLE001
                _LOGGER.error("Error checking EV stations for %s: %s", entity_id, ex)
                results[entity_id] = []

        _LOGGER.debug(
            "GPS EV station lookup for entities completed. Station counts per entity: %s",
            {ent_id: len(stations) for ent_id, stations in results.items()},
        )
        return results

    async def _ev_lookup_zip(self, service: ServiceCall) -> ServiceResponse:
        """Lookup EV stations via ZIP code."""
        zipcode = service.data[ATTR_POSTAL_CODE]

        limit = 5
        radius = 25
        solver = None

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]
        if ATTR_RADIUS in service.data:
            radius = service.data[ATTR_RADIUS]
        if ATTR_SOLVER in service.data:
            solver = service.data[ATTR_SOLVER]

        results = {}
        api = GasBuddy(
            solver_url=solver,
            cache_file=_cache_path(self.hass),
            session=async_get_clientsession(self.hass),
        )
        try:
            res = await api.price_lookup_service(zipcode=zipcode)
            lat = None
            lon = None
            if res.get("results"):
                lat = res["results"][0].get("latitude")
                lon = res["results"][0].get("longitude")
            if lat is not None and lon is not None:
                res = await api.ev_stations_nearby(lat=lat, lon=lon, radius=radius, limit=limit)
                results = {"stations": res.get("stations", [])}
            else:
                results = {"stations": [], "error": "Location coordinates not found for zip code"}
        except Exception as ex:  # noqa: BLE001
            _LOGGER.error("Error checking EV stations: %s", ex)
            results = {"stations": [], "error": str(ex)}

        _LOGGER.debug(
            "ZIP Code EV station lookup completed. Found %s stations. Error: %s",
            len(results.get("stations", [])),
            results.get("error"),
        )
        return results

    async def _clear_cache(self, service: ServiceCall) -> None:
        """Clear cache file."""
        data = service.data
        for device in data[ATTR_DEVICE_ID]:
            device_id = device
            _LOGGER.debug("Device ID: %s", device_id)

            dev_reg = dr.async_get(self.hass)
            device_entry = dev_reg.async_get(device_id)
            _LOGGER.debug("Device_entry: %s", device_entry)

            if not device_entry:
                raise ValueError(f"Device ID {device_id} is not valid")

            config_id = list(device_entry.connections)[0][1]
            _LOGGER.debug("Config ID: %s", config_id)
            manager = self.hass.data[DOMAIN][config_id][COORDINATOR]
            await manager.clear_cache()
