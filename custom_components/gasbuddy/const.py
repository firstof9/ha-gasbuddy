"""Constants for ha-gasbuddy."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from .entity import GasBuddySensorEntityDescription

# config flow
CONF_STATION_ID = "station_id"
CONF_INTERVAL = "interval"
CONF_NAME = "name"
CONF_POSTAL = "zipcode"
CONF_UOM = "uom"
CONF_GPS = "gps"
CONF_SOLVER = "solver"
CONF_TIMEOUT = "timeout"
CONF_EV_CHARGING = "ev_charging"
CONF_FETCH_GAS = "fetch_gas"
DEFAULT_INTERVAL = 3600
DEFAULT_NAME = "Gas Station"
DEFAULT_TIMEOUT = 60000
CONFIG_VER = 7

# hass.data attributes
ATTR_DEVICE_ID = "device_id"
ATTR_IMAGEURL = "image_url"
ATTR_LIMIT = "limit"
ATTR_RADIUS = "radius"
ATTR_POSTAL_CODE = "zipcode"
ATTR_SOLVER = "solver"
COORDINATOR = "coordinator"
SERVICES = "services"
DOMAIN = "gasbuddy"
VERSION = "1.0"
ISSUE_URL = "https://github.com/firstof9/ha-gasbuddy/issues"
PLATFORMS = ["sensor"]

# services
SERVICE_LOOKUP_GPS = "lookup_gps"
SERVICE_LOOKUP_ZIP = "lookup_zip"
SERVICE_EV_LOOKUP_GPS = "ev_lookup_gps"
SERVICE_EV_LOOKUP_ZIP = "ev_lookup_zip"
SERVICE_CLEAR_CACHE = "clear_cache"

# sensor constants
UNIT_OF_MEASURE = {
    "dollars_per_gallon": "gallon",
    "cents_per_liter": "liter",
}


SENSOR_TYPES: Final[dict[str, GasBuddySensorEntityDescription]] = {
    "last_updated": GasBuddySensorEntityDescription(
        name="Last Updated",
        key="last_updated",
        icon="mdi:update",
        price=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    "regular_gas": GasBuddySensorEntityDescription(
        key="regular_gas",
        name="Regular Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "midgrade_gas": GasBuddySensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "premium_gas": GasBuddySensorEntityDescription(
        key="premium_gas",
        name="Premium Gas",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "diesel": GasBuddySensorEntityDescription(
        key="diesel",
        name="Diesel",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "regular_gas_cash": GasBuddySensorEntityDescription(
        key="regular_gas",
        name="Regular Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "midgrade_gas_cash": GasBuddySensorEntityDescription(
        key="midgrade_gas",
        name="MidGrade Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "premium_gas_cash": GasBuddySensorEntityDescription(
        key="premium_gas",
        name="Premium Gas (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "diesel_cash": GasBuddySensorEntityDescription(
        key="diesel",
        name="Diesel (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # special fuels
    "e85": GasBuddySensorEntityDescription(
        key="e85",
        name="E85",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "e85_cash": GasBuddySensorEntityDescription(
        key="e85",
        name="E85 (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "e15": GasBuddySensorEntityDescription(
        key="e15",
        name="UNL88",
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "e15_cash": GasBuddySensorEntityDescription(
        key="e15",
        name="UNL88 (Cash)",
        cash=True,
        icon="mdi:gas-station",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # EV Charging Sensors
    "ev_level1": GasBuddySensorEntityDescription(
        key="ev_level1",
        name="EV Level 1 Chargers",
        icon="mdi:ev-station",
        price=False,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_level2": GasBuddySensorEntityDescription(
        key="ev_level2",
        name="EV Level 2 Chargers",
        icon="mdi:ev-station",
        price=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_dc_fast": GasBuddySensorEntityDescription(
        key="ev_dc_fast",
        name="EV DC Fast Chargers",
        icon="mdi:ev-station",
        price=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_j1772": GasBuddySensorEntityDescription(
        key="ev_j1772",
        name="EV J1772 Connectors",
        icon="mdi:ev-station",
        price=False,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_j1772_power": GasBuddySensorEntityDescription(
        key="ev_j1772_power",
        name="EV J1772 Connector Power",
        icon="mdi:lightning-bolt",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_ccs": GasBuddySensorEntityDescription(
        key="ev_ccs",
        name="EV CCS Connectors",
        icon="mdi:ev-station",
        price=False,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_ccs_power": GasBuddySensorEntityDescription(
        key="ev_ccs_power",
        name="EV CCS Connector Power",
        icon="mdi:lightning-bolt",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_chademo": GasBuddySensorEntityDescription(
        key="ev_chademo",
        name="EV CHAdeMO Connectors",
        icon="mdi:ev-station",
        price=False,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_chademo_power": GasBuddySensorEntityDescription(
        key="ev_chademo_power",
        name="EV CHAdeMO Connector Power",
        icon="mdi:lightning-bolt",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_nacs": GasBuddySensorEntityDescription(
        key="ev_nacs",
        name="EV NACS Connectors",
        icon="mdi:ev-station",
        price=False,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ev_nacs_power": GasBuddySensorEntityDescription(
        key="ev_nacs_power",
        name="EV NACS Connector Power",
        icon="mdi:lightning-bolt",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_status": GasBuddySensorEntityDescription(
        key="ev_status",
        name="EV Station Status",
        icon="mdi:check-circle-outline",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_network": GasBuddySensorEntityDescription(
        key="ev_network",
        name="EV Charging Network",
        icon="mdi:vector-difference-ba",
        price=False,
    ),
    "ev_network_web": GasBuddySensorEntityDescription(
        key="ev_network_web",
        name="EV Charging Network Website",
        icon="mdi:web",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_pricing": GasBuddySensorEntityDescription(
        key="ev_pricing",
        name="EV Charging Pricing",
        icon="mdi:cash",
        price=False,
    ),
    "ev_access_hours": GasBuddySensorEntityDescription(
        key="ev_access_hours",
        name="EV Access Hours",
        icon="mdi:clock-outline",
        price=False,
    ),
    "ev_access_code": GasBuddySensorEntityDescription(
        key="ev_access_code",
        name="EV Access Code",
        icon="mdi:lock-open-outline",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_cards_accepted": GasBuddySensorEntityDescription(
        key="ev_cards_accepted",
        name="EV Payment Accepted",
        icon="mdi:credit-card-outline",
        price=False,
        entity_registry_enabled_default=False,
    ),
    "ev_date_last_confirmed": GasBuddySensorEntityDescription(
        key="ev_date_last_confirmed",
        name="EV Last Confirmed",
        icon="mdi:calendar-check",
        price=False,
        entity_registry_enabled_default=False,
    ),
}
