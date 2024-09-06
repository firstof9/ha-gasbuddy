"""Constants for ha-gasbuddy."""

from __future__ import annotations

from typing import Final

from .entity import GasBuddySensorEntityDescription

# config flow
CONF_STATION_ID = "station_id"
CONF_INTERVAL = "interval"
CONF_NAME = "name"
CONF_POSTAL = "zipcode"
CONF_UOM = "uom"
DEFAULT_INTERVAL = 3600
DEFAULT_NAME = "Gas Station"

# hass.data attribues
COORDINATOR = "coordinator"
DOMAIN = "gasbuddy"
VERSION = "1.0"
ISSUE_URL = "https://github.com/firstof9/ha-gasbuddy/issues"
PLATFORMS = ["sensor"]

# sensor constants
UNIT_OF_MEASURE = {
    "dollars_per_gallon": "gallon",
    "cents_per_liter": "liter",
}


SENSOR_TYPES: Final[dict[str, GasBuddySensorEntityDescription]] = {
    "regular_gas": GasBuddySensorEntityDescription(
        key="regular_gas",
        name="Regular Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "midgrade_gas": GasBuddySensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "premium_gas": GasBuddySensorEntityDescription(
        key="premium_gas",
        name="Premium Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "diesel": GasBuddySensorEntityDescription(
        key="diesel",
        name="Diesel",
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "regular_gas_cash": GasBuddySensorEntityDescription(
        key="regular_gas",
        name="Regular Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "midgrade_gas_cash": GasBuddySensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "premium_gas_cash": GasBuddySensorEntityDescription(
        key="premium_gas",
        name="Premium Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
    "diesel_cash": GasBuddySensorEntityDescription(
        key="diesel",
        name="Diesel (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
    ),
}
