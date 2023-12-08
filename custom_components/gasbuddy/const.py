"""Constants for ha-gasbuddy."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

# config flow
CONF_STATION_ID = "station_id"
CONF_INTERVAL = "interval"
CONF_NAME = "name"
CONF_POSTAL = "zipcode"
DEFAULT_INTERVAL = 3600
DEFAULT_NAME = "Gas Station"

# hass.data attribues
COORDINATOR = "coordinator"
DOMAIN = "gasbuddy"
VERSION = "1.0"
ISSUE_URL = "https://github.com/firstof9/ha-gasbuddy/issues"
PLATFORMS = ['sensor']

# sensor constants
UNIT_OF_MEASURE = {
    "dollars_per_gallon": "gallon",
    "cents_per_liter": "liter",
}


SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    "regular_gas": SensorEntityDescription(
        key="regular_gas",
        name="Regular Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "midgrade_gas": SensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "premium_gas": SensorEntityDescription(
        key="premium_gas",
        name="Premium Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "diesel": SensorEntityDescription(
        key="diesel",
        name="Diesel",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
}
