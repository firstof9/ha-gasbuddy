"""GasBuddy services."""

import logging

import voluptuous as vol
from py_gasbuddy import GasBuddy
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_DEVICE_ID,
    ATTR_LIMIT,
    ATTR_POSTAL_CODE,
    COORDINATOR,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_LOOKUP_GPS,
    SERVICE_LOOKUP_ZIP,
)

_LOGGER = logging.getLogger(__name__)


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
            schema=vol.Schema(
                {
                    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                    vol.Optional(ATTR_LIMIT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=99)
                    ),
                }
            ),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            self._price_lookup_zip,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_POSTAL_CODE): cv.string,
                    vol.Optional(ATTR_LIMIT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=99)
                    ),
                }
            ),
            supports_response=SupportsResponse.ONLY,
        )
        self.hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            self._clear_cache,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
                }
            ),
        )

    # Setup services
    async def _price_lookup_gps(self, service: ServiceCall) -> ServiceResponse:
        """Lookup prices with GPS coordinates."""
        entity_ids = service.data[ATTR_ENTITY_ID]

        limit = 5

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]

        results = {}
        for entity_id in entity_ids:
            try:
                entity = self.hass.states.get(entity_id)
                lat = entity.attributes[ATTR_LATITUDE]
                lon = entity.attributes[ATTR_LONGITUDE]
                results[entity_id] = await GasBuddy().price_lookup_service(
                    lat=lat, lon=lon, limit=limit
                )
            except Exception as err:
                _LOGGER.error("Error checking prices: %s", err)

        _LOGGER.debug("GPS price lookup: %s", results)
        return results

    async def _price_lookup_zip(self, service: ServiceCall) -> ServiceResponse:
        """Lookup prices via ZIP code."""
        zipcode = service.data[ATTR_POSTAL_CODE]

        limit = 5

        if ATTR_LIMIT in service.data:
            limit = service.data[ATTR_LIMIT]

        results = {}
        try:
            results = await GasBuddy().price_lookup_service(
                zipcode=zipcode, limit=limit
            )
        except Exception as err:
            _LOGGER.error("Error checking prices: %s", err)

        _LOGGER.debug("ZIP Code price lookup: %s", results)
        return results

    async def _clear_cache(self, service: ServiceCall) -> ServiceResponse:
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
