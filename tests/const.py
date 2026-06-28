"""Constants for tests."""

from datetime import UTC, datetime
from types import MappingProxyType

from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_FETCH_GAS,
    CONF_FUEL_KEY,
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_PRICE_TYPE,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    DEFAULT_TIMEOUT,
)

# Hub config entry data
HUB_DATA = {
    CONF_NAME: "GasBuddy Hub",
    CONF_SOLVER: None,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_BRAND_ADJUSTMENTS: {},
}

# Station subentry data (replaces old CONFIG_DATA + options)
STATION_SUBENTRY_DATA = MappingProxyType({
    CONF_STATION_ID: 999001,
    CONF_NAME: "Gas Station",
    "latitude": 41.8781,
    "longitude": -87.6298,
    CONF_INTERVAL: 3600,
    CONF_UOM: True,
    CONF_GPS: True,
    CONF_EV_CHARGING: False,
    CONF_FETCH_GAS: True,
})

# Legacy config data (for migration tests)
CONFIG_DATA = {
    CONF_NAME: "Gas Station",
    CONF_INTERVAL: 3600,
    CONF_STATION_ID: 999001,
    CONF_UOM: True,
    CONF_GPS: True,
    CONF_SOLVER: None,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}

CONFIG_DATA_NO_UOM = {
    CONF_NAME: "Gas Station",
    CONF_STATION_ID: 999001,
}

OPTIONS_NO_UOM = {
    CONF_INTERVAL: 3600,
    CONF_UOM: False,
    CONF_GPS: True,
}

CONFIG_DATA_V1 = {
    CONF_NAME: "Gas Station",
    CONF_INTERVAL: 3600,
    CONF_STATION_ID: 999001,
    CONF_GPS: True,
}

STATION_LIST = {
    "999001": "Test Gas Co @ 100 Test Blvd",
    "999002": "Cheap Gas @ 200 Cheap St",
    "999003": "QuickFill @ 300 Quick Ave",
    "999004": "Budget Fuel @ 400 Budget Ln",
    "999005": "Value Stop @ 500 Value Rd",
    "999006": "Express Fill @ 600 Express Way",
    "999007": "Corner Gas @ 700 Corner St",
    "999008": "Highway Stop @ 800 Hwy 1",
    "999009": "Main St Gas @ 900 Main St",
    "999010": "Fuel Depot @ 1000 Depot Dr",
    "999011": "Green Pump @ 1100 Green Ave",
    "999012": "Fast Fill @ 1200 Fast Blvd",
    "999013": "Super Gas @ 1300 Super St",
    "999014": "Economy Fuel @ 1400 Economy Dr",
    "999015": "Town Gas @ 1500 Town Sq",
    "999016": "Metro Fill @ 1600 Metro Ave",
    "999017": "Prime Gas @ 1700 Prime Rd",
    "999018": "Peak Fuel @ 1800 Peak Blvd",
    "999019": "Central Gas @ 1900 Central Ave",
    "999020": "Park Gas @ 2000 Park Ln",
}

COORDINATOR_DATA = {
    "station_id": "999001",
    "name": "Test Gas Station",
    "pay_status": True,
    "image_url": "https://images.gasbuddy.io/b/test.png",
    "unit_of_measure": "dollars_per_gallon",
    "currency": "USD",
    "gps": True,
    "latitude": 41.8781,
    "longitude": -87.6298,
    "open_status": "open",
    "phone": "555-555-5555",
    "star_rating": 4.2,
    "address": {
        "line1": "100 Test Blvd",
        "locality": "Springfield",
        "region": "IL",
        "postalCode": "62701",
        "country": "US",
    },
    "amenities": [
        {"amenityId": 1, "name": "ATM"},
        {"amenityId": 2, "name": "Restrooms"},
    ],
    "regular_gas": {
        "credit": "Buddy_5bbkqrb1",
        "price": 2.95,
        "cash_price": None,
        "formatted_price": "$2.95",
        "deal_price": 2.78,
        "last_updated": "2023-12-10T17:48:46.584Z",
    },
    "premium_gas": {
        "credit": "Owner",
        "price": None,
        "cash_price": 3.35,
        "formatted_price": None,
        "deal_price": None,
        "last_updated": "2023-12-10T17:31:01.856Z",
    },
    "e85": {
        "credit": "Owner",
        "price": 2.83,
        "cash_price": None,
        "formatted_price": "$2.83",
        "deal_price": None,
        "last_updated": "2024-09-27T18:12:09.837Z",
    },
    "e15": {
        "credit": "Owner",
        "price": 3.33,
        "cash_price": 3.13,
        "formatted_price": "$3.33",
        "deal_price": None,
        "last_updated": "2024-09-27T18:12:09.837Z",
    },
    "last_updated": datetime(2025, 1, 9, 16, 12, 51, tzinfo=UTC),
}

CHEAPEST_SUBENTRY_DATA = MappingProxyType({
    CONF_NAME: "Cheapest Gas",
    CONF_CHEAPEST: True,
    CONF_FUEL_KEY: "regular_gas",
    CONF_PRICE_TYPE: "best",
    CONF_INTERVAL: 3600,
    CONF_UOM: True,
    CONF_GPS: False,
    CONF_EV_CHARGING: False,
    CONF_FETCH_GAS: True,
})

CONFIG_DATA_CHEAPEST = {
    CONF_NAME: "Cheapest Gas",
    CONF_CHEAPEST: True,
    CONF_FUEL_KEY: "regular_gas",
    CONF_PRICE_TYPE: "best",
    CONF_SOLVER: None,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}

OPTIONS_CHEAPEST = {
    CONF_INTERVAL: 3600,
    CONF_UOM: True,
    CONF_GPS: False,
    CONF_EV_CHARGING: False,
    CONF_FETCH_GAS: True,
}

COORDINATOR_DATA_CHEAPEST = {
    "station_id": "999002",
    "name": "Cheap Gas",
    "pay_status": True,
    "image_url": None,
    "unit_of_measure": "dollars_per_gallon",
    "currency": "USD",
    "latitude": 41.8800,
    "longitude": -87.6300,
    "distance": 0.5,
    "regular_gas": {
        "credit": "user99",
        "price": 2.89,
        "cash_price": 2.79,
        "formatted_price": "$2.89",
        "deal_price": 2.72,
        "last_updated": "2025-01-09T16:00:00.000Z",
    },
    "last_updated": datetime(2025, 1, 9, 16, 12, 51, tzinfo=UTC),
}

COORDINATOR_DATA_CAD = {
    "station_id": "999001",
    "image_url": None,
    "unit_of_measure": "cents_per_liter",
    "currency": "CAD",
    "gps": True,
    "latitude": 41.8781,
    "longitude": -87.6298,
    "regular_gas": {
        "credit": "Buddy_5bbkqrb1",
        "price": 143.9,
        "last_updated": "2023-12-10T17:48:46.584Z",
    },
    "premium_gas": {
        "credit": "Owner",
        "price": 153.1,
        "cash_price": 145.2,
        "last_updated": "2023-12-10T17:31:01.856Z",
    },
    "last_updated": datetime(2025, 1, 9, 16, 12, 51, tzinfo=UTC),
}
