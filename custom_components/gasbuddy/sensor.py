"""GasBuddy sensors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_IMAGEURL,
    CONF_NAME,
    CONF_STATION_ID,
    CONF_UOM,
    COORDINATOR,
    DOMAIN,
    SENSOR_TYPES,
    UNIT_OF_MEASURE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the GasBuddy sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    sensors = []
    for sensor in SENSOR_TYPES:  # pylint: disable=consider-using-dict-items
        sensors.append(GasBuddySensor(SENSOR_TYPES[sensor], coordinator, entry))

    async_add_entities(sensors, False)


class GasBuddySensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=too-many-instance-attributes
    """Implementation of a GasBuddy sensor."""

    def __init__(
        self,
        sensor_description: SensorEntityDescription,
        coordinator: str,
        config: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config
        self.entity_description = sensor_description
        self._name = sensor_description.name
        self._type = sensor_description.key
        self._unique_id = config.entry_id
        self._data = coordinator.data
        self.coordinator = coordinator
        self._state = None
        self._icon = sensor_description.icon
        self._cash = sensor_description.cash
        self._attr_name = f"{self._config.data[CONF_NAME]} {self._name}"
        self._attr_unique_id = f"{self._name}_{self._unique_id}"

    @property
    def device_info(self) -> dict:
        """Return a port description for device registry."""
        info = {
            "manufacturer": "GasBuddy",
            "name": self._config.data[CONF_NAME],
            "connections": {(DOMAIN, self._unique_id)},
        }

        return info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if data is None:
            self._state = None
        if self._type in data.keys():
            if self._cash and "cash_price" in data[self._type]:
                if self.coordinator.data["unit_of_measure"] == "cents_per_liter":
                    self._state = data[self._type]["cash_price"] / 100
                else:
                    self._state = data[self._type]["cash_price"]
            else:
                if self.coordinator.data["unit_of_measure"] == "cents_per_liter":
                    self._state = data[self._type]["price"] / 100
                else:
                    self._state = data[self._type]["price"]

        _LOGGER.debug("Sensor [%s] updated value: %s", self._type, self._state)
        return self._state

    @property
    def native_unit_of_measurement(self) -> Any:
        """Return the unit of measurement."""
        uom = self.coordinator.data["unit_of_measure"]
        currency = self.coordinator.data["currency"]
        if self._config.data[CONF_UOM]:
            if uom is not None and currency is not None:
                return f"{currency}/{UNIT_OF_MEASURE[uom]}"
        elif currency is not None:
            return currency
        return None

    @property
    def extra_state_attributes(self) -> Optional[dict]:
        """Return sesnsor attributes."""
        credit = self.coordinator.data[self._type]["credit"]
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = f"{credit} via GasBuddy"
        attrs["last_updated"] = self.coordinator.data[self._type]["last_updated"]
        attrs[CONF_STATION_ID] = self.coordinator.data[CONF_STATION_ID]
        attrs[ATTR_LATITUDE] = self.coordinator.data[ATTR_LATITUDE]
        attrs[ATTR_LONGITUDE] = self.coordinator.data[ATTR_LONGITUDE]
        return attrs

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if self.coordinator.data[ATTR_IMAGEURL] is not None:
            return self.coordinator.data[ATTR_IMAGEURL]

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        data = self.coordinator.data
        if self._type not in data or (self._type in data and data[self._type] is None):
            return False
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False
