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
CONFIG_VER = 4

# hass.data attribues
ATTR_IMAGEURL = "image_url"
ATTR_LIMIT = "limit"
COORDINATOR = "coordinator"
DOMAIN = "gasbuddy"
VERSION = "1.0"
ISSUE_URL = "https://github.com/firstof9/ha-gasbuddy/issues"
PLATFORMS = ["sensor"]

# services
SERVICE_LOOKUP_GPS = "lookup_gps"

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
        entity_registry_enabled_default=False,
    ),
    "regular_gas_cash": GasBuddySensorEntityDescription(
        key="regular_gas",
        name="Regular Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "midgrade_gas_cash": GasBuddySensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "premium_gas_cash": GasBuddySensorEntityDescription(
        key="premium_gas",
        name="Premium Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "diesel_cash": GasBuddySensorEntityDescription(
        key="diesel",
        name="Diesel (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    # special fuels
    "e85": GasBuddySensorEntityDescription(
        key="e85",
        name="E85",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "e85_cash": GasBuddySensorEntityDescription(
        key="e85",
        name="E85 (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "e15": GasBuddySensorEntityDescription(
        key="e15",
        name="UNL88",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    "e15_cash": GasBuddySensorEntityDescription(
        key="e15",
        name="UNL88 (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
}
