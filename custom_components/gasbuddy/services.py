"""GasBuddy services."""

import logging

import voluptuous as vol
from gasbuddy import GasBuddy  # pylint: disable=import-self
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

from .const import ATTR_LIMIT, DOMAIN, SERVICE_LOOKUP_GPS

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

    # Setup services
    async def _price_lookup_gps(self, service: ServiceCall) -> ServiceResponse:
        """Set the override."""
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
                results[entity_id] = await GasBuddy().price_lookup_gps(
                    lat=lat, lon=lon, limit=limit
                )
            except Exception as err:
                _LOGGER.error("Error checking prices: %s", err)

        _LOGGER.debug("GPS price lookup: %s", results)
        return results
