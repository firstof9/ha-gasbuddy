"""GasBuddy sensors."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_utc, parse_datetime

from .const import (
    ATTR_IMAGEURL,
    CONF_EV_CHARGING,
    CONF_FETCH_GAS,
    CONF_GPS,
    CONF_NAME,
    CONF_STATION_ID,
    CONF_UOM,
    COORDINATOR,
    DOMAIN,
    FUEL_KEY_CHOICES,
    SENSOR_TYPES,
    UNIT_OF_MEASURE,
)
from .coordinator import GasBuddyUpdateCoordinator
from .entity import GasBuddySensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the GasBuddy sensors."""
    coordinator: GasBuddyUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    ev_charging = entry.options.get(CONF_EV_CHARGING, False)
    fetch_gas = entry.options.get(CONF_FETCH_GAS, True)

    data = coordinator.data or {}
    fuels_available: set[str] = set()
    for fk in FUEL_KEY_CHOICES:
        if fk in data:
            fuels_available.add(fk)
    if isinstance(data.get("fuels"), list):
        fuels_available.update(data["fuels"])

    sensors = []
    for sensor_type, description in SENSOR_TYPES.items():
        if sensor_type.startswith("ev_") and not ev_charging:
            continue
        if (
            not sensor_type.startswith("ev_")
            and sensor_type not in {"last_updated", "open_status", "station_name"}
            and not fetch_gas
        ):
            continue

        enabled = description.entity_registry_enabled_default
        fuel_key = description.key

        if fuel_key in FUEL_KEY_CHOICES and data:
            if description.deal:
                enabled = (
                    fuel_key in fuels_available
                    and (data.get(fuel_key) or {}).get("deal_price") is not None
                )
            elif description.cash:
                enabled = (
                    fuel_key in fuels_available
                    and (data.get(fuel_key) or {}).get("cash_price") is not None
                )
            else:
                enabled = fuel_key in fuels_available

        mod_desc = dataclasses.replace(description, entity_registry_enabled_default=enabled)
        sensors.append(GasBuddySensor(mod_desc, coordinator, entry))

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
        self._deal = sensor_description.deal
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
            # `identifiers` is the correct field for application-defined
            # device keys; `connections` is reserved for hardware
            # connection tuples (mac/bluetooth/etc.). The `connections`
            # entry below is kept for one release so existing
            # installations keep matching their already-registered
            # device entry; it can be removed once users have migrated.
            identifiers={(DOMAIN, self._unique_id)},
            connections={(DOMAIN, self._unique_id)},
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not (data := self.coordinator.data) or self._type not in data:
            return None

        if not self._price:
            val = data.get(self._type)
            if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP and isinstance(
                val, str
            ):
                if parsed := parse_datetime(val):
                    return as_utc(parsed)
                _LOGGER.warning("Failed to parse timestamp for %s: %s", self._type, val)
                return None
            if self.entity_description.translation_key == "ev_access" and isinstance(val, str):
                return val.lower()
            return val

        if self._deal:
            price = data[self._type].get("deal_price")
        elif self._cash:
            price = data[self._type].get("cash_price")
        else:
            price = data[self._type].get("price")

        if price is None:
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
                return f"{currency}/{UNIT_OF_MEASURE.get(uom, uom)}"
        elif currency is not None:
            return currency
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return sesnsor attributes."""
        if not (data := self.coordinator.data):
            return None

        attrs: dict[str, Any] = {}

        if not self._price:
            if not self._type.startswith("ev_") and self._type not in {"open_status", "name"}:
                return None
            if self._type in {"open_status", "name"}:
                return None
            attrs[CONF_STATION_ID] = data.get(CONF_STATION_ID)
            attrs["station_name"] = data.get("ev_station_name")
            attrs["station_address"] = data.get("ev_station_address")
            if data.get("ev_distance_miles") is not None:
                attrs["distance_miles"] = data.get("ev_distance_miles")
            if data.get("ev_network") is not None:
                attrs["network"] = data.get("ev_network")
            if self._type == "ev_network" and data.get("ev_network_web") is not None:
                attrs["website"] = data.get("ev_network_web")
            if data.get("ev_pricing") is not None:
                attrs["pricing"] = data.get("ev_pricing")
            if data.get("ev_access_hours") is not None:
                attrs["access_hours"] = data.get("ev_access_hours")
            if self._config.options.get(CONF_GPS):
                attrs[ATTR_LATITUDE] = data.get(ATTR_LATITUDE)
                attrs[ATTR_LONGITUDE] = data.get(ATTR_LONGITUDE)
            return attrs

        if self._type not in data:
            return None

        if credit := data[self._type].get("credit"):
            attrs[ATTR_ATTRIBUTION] = f"{credit} via GasBuddy"

        attrs["last_updated"] = data[self._type].get("last_updated")
        attrs[CONF_STATION_ID] = data.get(CONF_STATION_ID)

        if fp := data[self._type].get("formatted_price"):
            attrs["formatted_price"] = fp
        if (dp := data[self._type].get("deal_price")) is not None:
            attrs["deal_price"] = dp
        if phone := data.get("phone"):
            attrs["phone"] = phone
        if rating := data.get("star_rating"):
            attrs["star_rating"] = rating
        if addr := data.get("address"):
            attrs["address"] = (
                f"{addr.get('line1', '')}, {addr.get('locality', '')}, {addr.get('region', '')}"
            )
        if amenities := data.get("amenities"):
            attrs["amenities"] = ", ".join(a["name"] for a in amenities if a.get("name"))

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

        if self._price:
            if self._deal:
                if data[self._type].get("deal_price") is None:
                    return False
            elif self._cash:
                if data[self._type].get("cash_price") is None:
                    return False
            elif data[self._type].get("price") is None:
                return False

        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False
