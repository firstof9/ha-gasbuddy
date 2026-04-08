"""GasBuddy sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_IMAGEURL,
    CONF_GPS,
    CONF_NAME,
    CONF_STATION_ID,
    CONF_UOM,
    COORDINATOR,
    DOMAIN,
    SENSOR_TYPES,
    UNIT_OF_MEASURE,
)
from .coordinator import GasBuddyUpdateCoordinator
from .entity import GasBuddySensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the GasBuddy sensors."""
    coordinator: GasBuddyUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    sensors = [
        GasBuddySensor(SENSOR_TYPES[sensor_type], coordinator, entry)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(sensors, False)


class GasBuddySensor(CoordinatorEntity, SensorEntity):  # pylint: disable=too-many-instance-attributes
    """Implementation of a GasBuddy sensor."""

    def __init__(
        self,
        sensor_description: GasBuddySensorEntityDescription,
        coordinator: GasBuddyUpdateCoordinator,
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
        self._cash = sensor_description.cash
        self._price = sensor_description.price

        self._attr_icon = sensor_description.icon
        self._attr_name = f"{self._config.data[CONF_NAME]} {self._name}"
        self._attr_unique_id = f"{self._name}_{self._unique_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a port description for device registry."""
        return DeviceInfo(
            manufacturer="GasBuddy",
            name=self._config.data[CONF_NAME],
            connections={(DOMAIN, self._unique_id)},
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not (data := self.coordinator.data) or self._type not in data:
            return None

        if not self._price:
            return data.get(self._type)

        if self._cash:
            price = data[self._type].get("cash_price")
        else:
            price = data[self._type].get("price")

        if not price:
            return None

        if data.get("unit_of_measure") == "cents_per_liter":
            self._state = price / 100
        else:
            self._state = price

        _LOGGER.debug("Sensor [%s] updated value: %s", self._type, self._state)
        return self._state

    @property
    def native_unit_of_measurement(self) -> Any:
        """Return the unit of measurement."""
        if not (data := self.coordinator.data) or not self._price:
            return None

        uom = data.get("unit_of_measure")
        currency = data.get("currency")

        if self._config.options.get(CONF_UOM):
            if uom is not None and currency is not None:
                return f"{currency}/{UNIT_OF_MEASURE[uom]}"
        elif currency is not None:
            return currency
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return sesnsor attributes."""
        if not self._price or not (data := self.coordinator.data) or self._type not in data:
            return None

        attrs: dict[str, Any] = {}
        if credit := data[self._type].get("credit"):
            attrs[ATTR_ATTRIBUTION] = f"{credit} via GasBuddy"

        attrs["last_updated"] = data[self._type].get("last_updated")
        attrs[CONF_STATION_ID] = data.get(CONF_STATION_ID)
        if self._config.options.get(CONF_GPS):
            attrs[ATTR_LATITUDE] = data.get(ATTR_LATITUDE)
            attrs[ATTR_LONGITUDE] = data.get(ATTR_LONGITUDE)
        return attrs

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if (data := self.coordinator.data) and data.get(ATTR_IMAGEURL):
            return data[ATTR_IMAGEURL]
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if (
            not (data := self.coordinator.data)
            or self._type not in data
            or data[self._type] is None
        ):
            return False
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False
