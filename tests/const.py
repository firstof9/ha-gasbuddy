"""Constants for tests."""

from datetime import datetime, timezone

from custom_components.gasbuddy.const import (
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_STATION_ID,
    CONF_UOM,
)

CONFIG_DATA = {
    CONF_NAME: "Gas Station",
    CONF_INTERVAL: 3600,
    CONF_STATION_ID: 208656,
    CONF_UOM: True,
    CONF_GPS: True,
}

CONFIG_DATA_NO_UOM = {
    CONF_NAME: "Gas Station",
    CONF_STATION_ID: 208656,
}

OPTIONS_NO_UOM = {
    CONF_INTERVAL: 3600,
    CONF_UOM: False,
    CONF_GPS: True,
}

CONFIG_DATA_V1 = {
    CONF_NAME: "Gas Station",
    CONF_INTERVAL: 3600,
    CONF_STATION_ID: 208656,
    CONF_GPS: True,
}

STATION_LIST = {
    "187725": "Shell @ 1520 N Verrado Way",
    "208656": "Costco @ 1101 N Verrado Way",
    "87490": "Chevron @ 1419 N 195th Ave",
    "110402": "Circle K @ 721 N 195th Ave",
    "203982": "Fry's @ 19600 W Indian School Rd",
    "126744": "Circle K @ 537 S Watson Rd",
    "201250": "QuikTrip @ 900 S Watson Rd",
    "38363": "Fry's @ 1300 S Watson Rd",
    "27487": "Love's Travel Stop @ 1610 N Miller Rd",
    "160044": "QuikTrip @ 1850 S Miller Rd",
    "135437": "Chevron @ 2075 S Miller Rd",
    "130812": "Fry's @ 16380 W Yuma Rd",
    "200905": "Circle K @ 15535 W McDowell Rd",
    "85320": "Safeway @ 440 N Estrella Pkwy",
    "155795": "QuikTrip @ 575 N Estrella Pkwy",
    "118417": "Circle K @ 307 E US-85",
    "154238": "Chevron @ 825 E Monroe Ave",
    "150938": "Shell @ 501 E Monroe Ave",
    "209199": "QuikTrip @ 1540 N Bullard Ave",
    "27442": "Safeway @ 14175 W Indian School Rd",
}

COORDINATOR_DATA = {
    "station_id": "208656",
    "image_url": "https://images.gasbuddy.io/b/122.png",
    "unit_of_measure": "dollars_per_gallon",
    "currency": "USD",
    "gps": True,
    "latitude": 33.459108,
    "longitude": -112.502745,
    "regular_gas": {
        "credit": "Buddy_5bbkqrb1",
        "price": 2.95,
        "last_updated": "2023-12-10T17:48:46.584Z",
    },
    "premium_gas": {
        "credit": "Owner",
        "price": None,
        "cash_price": 3.35,
        "last_updated": "2023-12-10T17:31:01.856Z",
    },
    "e85": {
        "credit": "Owner",
        "price": 2.83,
        "cash_price": None,
        "last_updated": "2024-09-27T18:12:09.837Z",
    },
    "e15": {
        "credit": "Owner",
        "price": 3.33,
        "cash_price": 3.13,
        "last_updated": "2024-09-27T18:12:09.837Z",
    },
    "last_updated": datetime(2025, 1, 9, 16, 12, 51, tzinfo=timezone.utc),
}

COORDINATOR_DATA_CAD = {
    "station_id": "208656",
    "image_url": None,
    "unit_of_measure": "cents_per_liter",
    "currency": "CAD",
    "gps": True,
    "latitude": 33.459108,
    "longitude": -112.502745,
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
    "last_updated": datetime(2025, 1, 9, 16, 12, 51, tzinfo=timezone.utc),
}
