"""Test gasbuddy sensors."""

import copy
import json
from unittest.mock import patch

from py_gasbuddy.exceptions import APIError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SHOW_DISCOUNTED,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    COORDINATOR,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SENSOR_TYPES,
    SERVICE_LOOKUP_GPS,
)
from custom_components.gasbuddy.coordinator import (
    GasBuddyUpdateCoordinator,
    _redact,  # noqa: PLC2701
    format_address,
)
from custom_components.gasbuddy.sensor import GasBuddySensor
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.dt import as_utc, parse_datetime
from tests.common import load_fixture
from tests.conftest import _make_cheapest_subentry, _make_hub_entry, _make_station_subentry

from .const import (
    CONFIG_DATA,
    CONFIG_DATA_CHEAPEST,
    CONFIG_DATA_NO_UOM,
    COORDINATOR_DATA,
    HUB_DATA,
    OPTIONS_CHEAPEST,
    OPTIONS_NO_UOM,
)

ATTR_ENTITY_PICTURE = "entity_picture"

pytestmark = pytest.mark.asyncio


async def test_sensors(hass, mock_gasbuddy, entity_registry: er.EntityRegistry):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # With enriched COORDINATOR_DATA: regular_gas, premium_gas, premium_gas_cash,
    # e85, e15, e15_cash, regular_gas_deal, last_updated = 8 enabled sensors
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.95"
    assert state.attributes["unit_of_measurement"] == "USD/gallon"
    assert state.attributes[ATTR_LATITUDE] == 41.8781
    assert state.attributes[ATTR_LONGITUDE] == -87.6298
    assert state.attributes[ATTR_ENTITY_PICTURE] == "https://images.gasbuddy.io/b/test.png"

    # midgrade_gas not in station data → disabled by dynamic enabled_default → no state
    assert hass.states.get("sensor.gas_station_midgrade_gas") is None

    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "unavailable"

    # regular_gas_cash is disabled (cash_price=None in fixture)
    entity_id = "sensor.gas_station_regular_gas_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    # cash_price=None → unavailable after enable
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"

    state = hass.states.get("sensor.gas_station_last_updated")
    assert state
    assert state.state == "2025-01-09T16:12:51+00:00"


async def test_sensors_no_uom(hass, mock_gasbuddy, entity_registry: er.EntityRegistry):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA_NO_UOM,
        options=OPTIONS_NO_UOM,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.95"
    assert state.attributes["unit_of_measurement"] == "USD"
    assert state.attributes[ATTR_LATITUDE] == 41.8781
    assert state.attributes[ATTR_LONGITUDE] == -87.6298

    # midgrade_gas not in station data → disabled by dynamic enabled_default → no state
    assert hass.states.get("sensor.gas_station_midgrade_gas") is None

    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "unavailable"

    # e85_cash is disabled (cash_price=None in fixture)
    entity_id = "sensor.gas_station_e85_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_sensors_cad(hass, mock_gasbuddy_cad, entity_registry: er.EntityRegistry):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # CAD data has regular_gas + premium_gas + premium_gas_cash (cash=145.2) + last_updated = 4
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "1.439"
    assert state.attributes["unit_of_measurement"] == "CAD/liter"
    assert state.attributes[ATTR_LATITUDE] == 41.8781
    assert state.attributes[ATTR_LONGITUDE] == -87.6298
    assert ATTR_ENTITY_PICTURE not in state.attributes

    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state is None

    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "1.531"

    # premium_gas_cash is now enabled (cash_price=145.2 present)
    state = hass.states.get("sensor.gas_station_premium_gas_cash")
    assert state
    assert state.state == "1.452"

    # regular_gas_cash remains disabled (no cash_price key in CAD regular_gas fixture)
    entity_id = "sensor.gas_station_regular_gas_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_sensor_robustness(hass, mock_gasbuddy, integration):
    """Test sensor behavior with missing or null coordinator data."""

    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    # Test with empty data
    with patch.dict(coordinator.data, {}, clear=True):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None
        assert sensor.native_unit_of_measurement is None

    # Test with None data
    with patch.object(coordinator, "data", None):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None
        assert sensor.native_unit_of_measurement is None

    # Test with missing sensor key
    with patch.object(coordinator, "data", {"unit_of_measure": "dollars_per_gallon"}):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None

    # Test extra_state_attributes early return for non-price sensors
    sensor = GasBuddySensor(SENSOR_TYPES["last_updated"], coordinator, integration)
    assert sensor.extra_state_attributes is None


async def test_coordinator_success(hass, mock_aioclient):
    """Test coordinator successful data fetch."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA, CONF_STATION_ID: "999001", CONF_TIMEOUT: DEFAULT_TIMEOUT},
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_aioclient.get("https://www.gasbuddy.com/home", status=200, text=load_fixture("index.html"))
    mock_aioclient.post(
        "https://www.gasbuddy.com/graphql", status=200, text=load_fixture("station.json")
    )

    # This will call _async_update_data UNPATCHED
    data = await coordinator._async_update_data()  # noqa: SLF001
    assert "last_updated" in data
    assert data["station_id"] == "32394"


async def test_sensor_coverage_edge_cases(hass, mock_gasbuddy, integration):
    """Test sensor edge cases for 100% coverage."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    # Test: price is 0 — valid price, sensor is available and returns 0
    with patch.dict(
        coordinator.data,
        {"regular_gas": {"price": 0, "last_updated": "2023-12-10T17:48:46.584Z"}},
    ):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.available is True
        assert sensor.native_value == 0

    # Test: price is None — native_value returns None (sensor.py line 148)
    with patch.dict(
        coordinator.data,
        {"regular_gas": {"price": None, "last_updated": "2023-12-10T17:48:46.584Z"}},
    ):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_value is None

    # Test Line 115: currency and uom missing when CONF_UOM is True
    with patch.dict(coordinator.data, {"unit_of_measure": None, "currency": None}):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_unit_of_measurement is None

    # Test Line 115: currency missing when CONF_UOM is False
    hass.config_entries.async_update_entry(integration, options={CONF_UOM: False})
    with patch.dict(coordinator.data, {"currency": None}):
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
        assert sensor.native_unit_of_measurement is None


async def test_ev_sensors(hass, mock_gasbuddy, integration):
    """Test EV charging sensors and their attributes."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    ev_data = {
        "station_id": "999001",
        "ev_level1": 0,
        "ev_level2": 2,
        "ev_dc_fast": 4,
        "ev_station_name": "Test EV Station",
        "ev_station_address": "100 Test Blvd",
        "ev_distance_miles": 1.5,
        "ev_network": "TestNetwork",
        "ev_network_web": "https://testnetwork.example.com",
        "ev_pricing": "Free",
        "ev_access_hours": "24/7",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "ev_date_last_confirmed": "2026-05-18",
        "ev_access_code": "None",
    }

    with patch.dict(coordinator.data, ev_data):
        sensor = GasBuddySensor(SENSOR_TYPES["ev_level2"], coordinator, integration)
        assert sensor.native_value == 2

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs[CONF_STATION_ID] == "999001"
        assert attrs["station_name"] == "Test EV Station"
        assert attrs["station_address"] == "100 Test Blvd"
        assert attrs["distance_miles"] == 1.5
        assert attrs["network"] == "TestNetwork"
        assert attrs["pricing"] == "Free"
        assert attrs["access_hours"] == "24/7"
        assert attrs[ATTR_LATITUDE] == 41.8781
        assert attrs[ATTR_LONGITUDE] == -87.6298
        assert "website" not in attrs

        # Test ev_network sensor which has the website attribute
        sensor_web = GasBuddySensor(SENSOR_TYPES["ev_network"], coordinator, integration)
        attrs_web = sensor_web.extra_state_attributes
        assert attrs_web is not None
        assert attrs_web["network"] == "TestNetwork"
        assert attrs_web["website"] == "https://testnetwork.example.com"

        # Test ev_date_last_confirmed sensor
        sensor_date = GasBuddySensor(
            SENSOR_TYPES["ev_date_last_confirmed"], coordinator, integration
        )
        assert sensor_date.native_value == as_utc(parse_datetime("2026-05-18"))

        # Test invalid date string for TIMESTAMP sensor returns None
        with patch.dict(coordinator.data, {"ev_date_last_confirmed": "invalid-date"}):
            assert sensor_date.native_value is None

        # Test ev_access_code sensor
        sensor_access = GasBuddySensor(SENSOR_TYPES["ev_access_code"], coordinator, integration)
        assert sensor_access.native_value == "none"


async def test_sensors_ev_only(hass, mock_gasbuddy, entity_registry: er.EntityRegistry):
    """Test setup_entry with EV charging enabled and gas sensors disabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EV Only Station",
        data=CONFIG_DATA,
        options={
            CONF_EV_CHARGING: True,
            CONF_FETCH_GAS: False,
        },
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get states
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    # Gas sensors should be filtered out
    # "last_updated" is kept, and EV sensors are kept
    assert "sensor.gas_station_regular_gas" not in states
    assert "sensor.gas_station_last_updated" in states
    assert "sensor.gas_station_ev_level_2_chargers" in states


async def test_redact_fallback():
    """Test coordinator._redact fallback logic when JSON serialization fails."""

    class UnserializableKey:
        def __str__(self):
            return "UnserializableKey"

    # A dict with an unserializable key fails json.dumps but succeeds on str()
    bad_dict = {UnserializableKey(): "value", "latitude": 12.34}
    redacted = _redact(bad_dict)
    assert "UnserializableKey" in redacted
    assert "value" in redacted
    assert "12.34" not in redacted
    assert "**REDACTED**" in redacted


async def test_dynamic_enabled_deal(hass, mock_gasbuddy, entity_registry: er.EntityRegistry):
    """Test that deal sensors are enabled only when deal_price is present."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # regular_gas has deal_price=2.78 → deal sensor should be enabled
    deal_entry = entity_registry.async_get("sensor.gas_station_regular_gas_deal")
    assert deal_entry is not None
    assert not deal_entry.disabled

    # premium_gas has deal_price=None → deal sensor should be disabled
    premium_deal_entry = entity_registry.async_get("sensor.gas_station_premium_gas_deal")
    assert premium_deal_entry is not None
    assert premium_deal_entry.disabled

    # e85 has deal_price=None → deal sensor should be disabled
    e85_deal_entry = entity_registry.async_get("sensor.gas_station_e85_deal")
    assert e85_deal_entry is not None
    assert e85_deal_entry.disabled


async def test_deal_native_value(hass, mock_gasbuddy, integration):
    """Test deal sensor returns deal_price."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    sensor = GasBuddySensor(SENSOR_TYPES["regular_gas_deal"], coordinator, integration)
    # regular_gas.deal_price = 2.78
    assert sensor.native_value == 2.78


async def test_deal_sensor_unavailable(hass, mock_gasbuddy, integration):
    """Test deal sensor is unavailable when deal_price is None."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    # premium_gas.deal_price = None
    sensor = GasBuddySensor(SENSOR_TYPES["premium_gas_deal"], coordinator, integration)
    assert sensor.available is False


async def test_open_status_sensor(hass, mock_gasbuddy, integration):
    """Test open_status sensor returns the station status string."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    sensor = GasBuddySensor(SENSOR_TYPES["open_status"], coordinator, integration)
    assert sensor.native_value == "open"
    # open_status is a non-price, non-EV sensor → no extra attributes
    assert sensor.extra_state_attributes is None


async def test_station_name_sensor(hass, mock_gasbuddy, integration):
    """Test station_name sensor returns the station name string."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    sensor = GasBuddySensor(SENSOR_TYPES["station_name"], coordinator, integration)
    assert sensor.native_value == "Test Gas Station"
    assert sensor.extra_state_attributes is None


async def test_extra_attrs_richer(hass, mock_gasbuddy, integration):
    """Test price sensor attributes include new enriched fields."""
    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]

    sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
    attrs = sensor.extra_state_attributes

    assert attrs is not None
    assert attrs.get("formatted_price") == "$2.95"
    assert attrs.get("deal_price") == 2.78
    assert attrs.get("phone") == "555-555-5555"
    assert attrs.get("star_rating") == 4.2
    assert attrs.get("address") == "100 Test Blvd, Springfield, IL, 62701, US"
    assert attrs.get("amenities") == "ATM, Restrooms"


async def test_deal_sensor_enabled_without_pay_status(
    hass, mock_gasbuddy, entity_registry: er.EntityRegistry
):
    """Deal sensors enable when deal_price is present even without pay_status (cheapest mode)."""
    data_cheapest_like = {
        **COORDINATOR_DATA,
        "regular_gas": {**COORDINATOR_DATA["regular_gas"], "deal_price": 2.50},
    }
    data_cheapest_like.pop("pay_status", None)
    with patch(
        "custom_components.gasbuddy.GasBuddyUpdateCoordinator._async_update_data",
        return_value=data_cheapest_like,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Gas Station",
            data=CONFIG_DATA,
            options={CONF_UOM: True, "gps": True, CONF_EV_CHARGING: False, CONF_FETCH_GAS: True},
            version=2,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    deal_entry = entity_registry.async_get("sensor.gas_station_regular_gas_deal")
    assert deal_entry is not None
    assert not deal_entry.disabled


async def test_extra_attrs_deal_price_present_without_pay_status(hass, mock_gasbuddy, integration):
    """deal_price attribute appears when deal_price is set, even without pay_status (cheapest mode)."""

    coordinator = hass.data[DOMAIN][integration.entry_id][COORDINATOR]
    original_data = coordinator.data
    patched_data = copy.deepcopy(original_data)
    patched_data.pop("pay_status", None)
    coordinator.data = patched_data

    sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, integration)
    attrs = sensor.extra_state_attributes

    coordinator.data = original_data  # restore

    assert attrs is not None
    assert "deal_price" in attrs
    assert attrs["deal_price"] == patched_data["regular_gas"]["deal_price"]


# ---------------------------------------------------------------------------
# Coordinator cheapest-mode tests (coordinator.py lines 95, 247-290)
# ---------------------------------------------------------------------------

_CHEAPEST_STATIONS = [
    {
        "station_id": "111",
        "name": "Expensive",
        "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": 3.80},
    },
    {
        "station_id": "222",
        "name": "Cheap",
        "regular_gas": {"price": 3.20, "cash_price": 3.10, "deal_price": 3.00},
    },
]


async def test_coordinator_cheapest_gps(hass):
    """Cheapest mode picks lowest station via GPS (best price type)."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=2
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": _CHEAPEST_STATIONS},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["station_id"] == "222"
    assert "last_updated" in data


async def test_coordinator_cheapest_postal(hass):
    """Cheapest mode uses postal code when configured."""

    config = {**CONFIG_DATA_CHEAPEST, CONF_POSTAL: "12345"}
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=2)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    stations = [
        {
            "station_id": "333",
            "name": "Postal",
            "regular_gas": {"price": 3.10, "cash_price": None, "deal_price": None},
        }
    ]
    with patch.object(coordinator._api, "price_lookup_service", return_value={"results": stations}):  # noqa: SLF001
        data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["station_id"] == "333"


async def test_coordinator_cheapest_no_stations(hass):
    """Cheapest mode raises UpdateFailed when no station carries the fuel."""

    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=2
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with (
        patch.object(coordinator._api, "price_lookup_service", return_value={"results": []}),  # noqa: SLF001
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_coordinator_cheapest_api_error(hass):
    """Cheapest mode wraps API errors as UpdateFailed."""

    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=2
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with (
        patch.object(coordinator._api, "price_lookup_service", side_effect=APIError("boom")),  # noqa: SLF001
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_coordinator_cheapest_sort_deal(hass):
    """Cheapest mode sort by deal price."""

    config = {**CONFIG_DATA_CHEAPEST, CONF_PRICE_TYPE: "deal"}
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=2)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": _CHEAPEST_STATIONS},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"


async def test_coordinator_cheapest_sort_cash(hass):
    """Cheapest mode sort by cash price."""

    config = {**CONFIG_DATA_CHEAPEST, CONF_PRICE_TYPE: "cash"}
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=2)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": _CHEAPEST_STATIONS},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"


async def test_coordinator_cheapest_sort_credit(hass):
    """Cheapest mode sort by credit price (fallback else branch)."""

    config = {**CONFIG_DATA_CHEAPEST, CONF_PRICE_TYPE: "credit"}
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=2)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": _CHEAPEST_STATIONS},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"


async def test_coordinator_cheapest_filtering(hass):
    """Test coordinator filtering in cheapest mode."""

    stations = [
        {
            "station_id": "111",
            "name": "Expensive Station",
            "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": 3.80},
            "brands": [{"brandId": "brand_exp", "name": "Brand Exp"}],
        },
        {
            "station_id": "222",
            "name": "Cheap Station",
            "regular_gas": {"price": 3.20, "cash_price": 3.10, "deal_price": 3.00},
            "brands": [{"brandId": "brand_cheap", "name": "Brand Cheap"}],
        },
    ]

    # Test 1: Exclude the cheapest brand (should select Expensive)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_EXCLUDE_BRANDS: ["brand_cheap"],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=8)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"

    # Test 2: Include only the expensive brand (should select Expensive)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_INCLUDE_BRANDS: ["brand_exp"],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=8)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"

    # Test 3: Exclude the cheapest station (should select Expensive)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_EXCLUDE_STATIONS: ["222"],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=8)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"

    # Test 4: Include only the expensive station (should select Expensive)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_INCLUDE_STATIONS: ["111"],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=8)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"


async def test_coordinator_cheapest_filtering_no_stations(hass):
    """Test coordinator filtering in cheapest mode raises UpdateFailed if no stations remain."""

    stations = [
        {
            "station_id": "111",
            "name": "Expensive Station",
            "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": 3.80},
            "brands": [{"brandId": "brand_exp", "name": "Brand Exp"}],
        },
    ]

    # Exclude the only station's brand (should raise UpdateFailed)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_EXCLUDE_BRANDS: ["brand_exp"],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=8)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with (
        patch.object(
            coordinator._api,  # noqa: SLF001
            "price_lookup_service",
            return_value={"results": stations},
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_fuels_list_enables_sensors(hass, entity_registry: er.EntityRegistry):
    """Fuels list in coordinator data enables sensors for carried fuels (sensor.py line 48)."""
    data_with_fuels = {**COORDINATOR_DATA, "fuels": ["regular_gas", "diesel"]}
    with patch(
        "custom_components.gasbuddy.GasBuddyUpdateCoordinator._async_update_data",
        return_value=data_with_fuels,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="gas_station",
            data=CONFIG_DATA,
            options={CONF_UOM: True, "gps": True, CONF_EV_CHARGING: False, CONF_FETCH_GAS: True},
            version=2,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diesel = entity_registry.async_get("sensor.gas_station_diesel")
    assert diesel is not None
    assert diesel.disabled_by is None


async def test_coordinator_cheapest_no_valid_prices(hass):
    """Cheapest mode raises UpdateFailed when all stations have no finite price."""

    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=2
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    stations_no_price = [
        {
            "station_id": "999",
            "name": "NoPriceStation",
            "regular_gas": {"price": None, "cash_price": None, "deal_price": None},
        },
    ]
    with (
        patch.object(
            coordinator._api,  # noqa: SLF001
            "price_lookup_service",
            return_value={"results": stations_no_price},
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


async def test_price_lookup_gps_no_coordinates(hass, integration, caplog):
    """GPS price lookup skips entities without lat/lon and logs a warning."""
    # Register a state with no GPS attributes
    hass.states.async_set("sensor.no_gps_entity", "on", {})

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_LOOKUP_GPS,
        {ATTR_ENTITY_ID: ["sensor.no_gps_entity"]},
        blocking=True,
        return_response=True,
    )

    assert result.get("sensor.no_gps_entity") == {}
    assert any("lacks latitude/longitude" in rec.message for rec in caplog.records)


async def test_coordinator_cheapest_brand_adjustments(hass):
    """Test coordinator brand adjustments in cheapest mode."""
    stations = [
        {
            "station_id": "111",
            "name": "Expensive Station",
            "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": 3.80},
            "brands": [{"brandId": "brand_exp", "name": "Brand Exp"}],
        },
        {
            "station_id": "222",
            "name": "Cheap Station",
            "regular_gas": {"price": 3.50, "cash_price": 3.40, "deal_price": 3.30},
            "brands": [{"brandId": "brand_cheap", "name": "Brand Cheap"}],
        },
    ]

    # Without brand adjustments, Cheap Station (222) is cheapest
    config = {
        **CONFIG_DATA_CHEAPEST,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"

    # With brand adjustments by ID matching, give Expensive Station a $0.60 discount
    # so its effective price is 3.40 (vs 3.50), making it cheaper.
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_BRAND_ADJUSTMENTS: {"brand_exp": -0.60},
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"

    # With brand adjustments by name matching (case-insensitive), give Expensive Station $0.60 discount
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_BRAND_ADJUSTMENTS: {"brand exp": -0.60},
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "111"


async def test_coordinator_cheapest_brand_adjustments_edge_cases(hass):
    """Test edge cases in coordinator brand adjustments (invalid types and missing price)."""
    stations = [
        {
            "station_id": "111",
            "name": "Expensive Station",
            "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": 3.80},
            "brands": [{"brandId": "brand_exp", "name": "Brand Exp"}],
        },
        {
            "station_id": "222",
            "name": "Cheap Station",
            "regular_gas": {"price": 3.50, "cash_price": 3.40, "deal_price": 3.30},
            "brands": [{"brandId": "brand_cheap", "name": "Brand Cheap"}],
        },
    ]

    # Test ValueError/TypeError in brand ID lookup (invalid strings/types)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_BRAND_ADJUSTMENTS: {"brand_exp": "invalid_float", "brand_cheap": []},
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"

    # Test ValueError/TypeError in brand Name lookup (invalid strings/types)
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_BRAND_ADJUSTMENTS: {"brand exp": "invalid_float", "brand cheap": []},
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"

    # Test val is None in adjust (when price type is deal but deal_price is None/missing)
    stations_missing_deal = [
        {
            "station_id": "111",
            "name": "Station A",
            "regular_gas": {"price": 4.00, "cash_price": 3.90, "deal_price": None},
            "brands": [{"brandId": "brand_exp", "name": "Brand Exp"}],
        },
        {
            "station_id": "222",
            "name": "Station B",
            "regular_gas": {"price": 3.50, "cash_price": 3.40, "deal_price": 3.30},
            "brands": [{"brandId": "brand_cheap", "name": "Brand Cheap"}],
        },
    ]
    config = {
        **CONFIG_DATA_CHEAPEST,
        CONF_PRICE_TYPE: "deal",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, options=OPTIONS_CHEAPEST, version=9)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations_missing_deal},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert data["station_id"] == "222"


async def test_coordinator_cheapest_station_address(hass):
    """Cheapest coordinator flattens the address dict into station_address.

    Covers coordinator.py: the if-addr block in _async_update_cheapest that produces
    a formatted station_address string from the raw address dict.
    """
    stations = [
        {
            "station_id": "400",
            "name": "Address Station",
            "address": {
                "line1": "123 Main St",
                "locality": "Springfield",
                "region": "IL",
                "postalCode": "62701",
                "country": "US",
            },
            "regular_gas": {"price": 3.10, "cash_price": None, "deal_price": None},
        }
    ]
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=9
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["station_address"] == "123 Main St, Springfield, IL, 62701, US"


async def test_coordinator_cheapest_station_address_empty(hass):
    """Cheapest coordinator leaves station_address key unset if address fields are empty/None."""
    # Test 1: Empty strings inside address dict
    stations_empty_fields = [
        {
            "station_id": "400",
            "name": "Empty Address Station",
            "address": {
                "line1": "",
                "locality": "",
                "region": "",
            },
            "regular_gas": {"price": 3.10, "cash_price": None, "deal_price": None},
        }
    ]
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_CHEAPEST, options=OPTIONS_CHEAPEST, version=9
    )
    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations_empty_fields},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert "station_address" not in data

    # Test 2: Address is None/missing entirely
    stations_no_address = [
        {
            "station_id": "400",
            "name": "Empty Address Station",
            "address": None,
            "regular_gas": {"price": 3.10, "cash_price": None, "deal_price": None},
        }
    ]
    with patch.object(
        coordinator._api,  # noqa: SLF001
        "price_lookup_service",
        return_value={"results": stations_no_address},
    ):
        data = await coordinator._async_update_data()  # noqa: SLF001
    assert "station_address" not in data


def test_format_address_helper():
    """Verify that format_address helper handles None and empty values correctly."""
    assert format_address(None) is None
    assert format_address({}) is None
    assert format_address({"line1": "  ", "locality": ""}) is None


async def test_cheapest_station_address_sensor_state(hass, mock_gasbuddy_cheapest):
    """station_address sensor appears on cheapest subentries with correct state.

    Also verifies the sensor is absent on regular (non-cheapest) station subentries.
    """
    cheapest_sub = _make_cheapest_subentry()
    entry = _make_hub_entry(hass, subentries=[cheapest_sub])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # station_address is disabled by default — verify it exists in the entity registry
    entity_registry = er.async_get(hass)
    address_entries = [
        e
        for e in entity_registry.entities.values()
        if e.config_subentry_id == "cheapest_subentry_id"
        and e.domain == "sensor"
        and "station_address" in e.entity_id
    ]
    assert len(address_entries) == 1, (
        "station_address sensor must be registered for cheapest subentry"
    )
    assert address_entries[0].disabled_by is not None, "sensor must be disabled by default"

    # Enable the sensor and verify its state
    entity_registry.async_update_entity(address_entries[0].entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(address_entries[0].entity_id)
    assert state is not None
    assert state.state == "400 4th St SE, Rochester, MN, 55904, US"

    # station_address must NOT be registered for any non-cheapest subentry
    regular_address = [
        e
        for e in entity_registry.entities.values()
        if e.domain == "sensor"
        and "station_address" in e.entity_id
        and e.config_subentry_id != "cheapest_subentry_id"
    ]
    assert regular_address == [], "station_address sensor should not appear on regular stations"


async def test_sensor_brand_adjustments_options(hass, mock_aioclient):
    """Test sensor behavior with brand adjustments, discounted_price attribute and state toggle."""
    graphql_response_usd = {
        "data": {
            "station": {
                "id": "999001",
                "name": "Cheap Station",
                "phone": "(507)281-3105",
                "openStatus": "open",
                "priceUnit": "dollars_per_gallon",
                "currency": "USD",
                "latitude": 41.8781,
                "longitude": -87.6298,
                "brands": [
                    {
                        "brandId": "brand_cheap",
                        "brandingType": "fuel",
                        "imageUrl": "https://images.gasbuddy.io/b/165.png",
                        "name": "Brand Cheap",
                    }
                ],
                "prices": [
                    {
                        "cash": None,
                        "credit": {
                            "nickname": "tigerdoodles",
                            "postedTime": "2026-05-19T15:02:49.375Z",
                            "price": 3.00,
                            "formattedPrice": "$3.00",
                        },
                        "fuelProduct": "regular_gas",
                        "longName": "Regular",
                    }
                ],
            }
        }
    }

    mock_aioclient.get("https://www.gasbuddy.com/home", status=200, text=load_fixture("index.html"))
    mock_aioclient.post(
        "https://www.gasbuddy.com/graphql",
        status=200,
        text=json.dumps(graphql_response_usd),
    )

    sub_data = {
        CONF_NAME: "Gas Station",
        CONF_STATION_ID: "999001",
        CONF_INTERVAL: 3600,
        CONF_UOM: True,
        CONF_GPS: True,
        CONF_FETCH_GAS: True,
        CONF_SHOW_DISCOUNTED: False,
    }
    sub = _make_station_subentry(
        data=sub_data,
        title="Gas Station",
        unique_id="999001",
        subentry_id="test_subentry_id",
    )
    hub_data = {
        CONF_NAME: "GasBuddy Hub",
        CONF_SOLVER: "",
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_BRAND_ADJUSTMENTS: {"brand_cheap": -0.10},
    }
    entry = _make_hub_entry(hass, hub_data=hub_data, subentries=[sub])
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The regular gas state should show the actual pump price (3.00)
    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "3.0"
    # But the discounted_price attribute should reflect the $0.10 discount
    assert state.attributes.get("discounted_price") == 2.90

    # 2. Test with show_discounted=True
    # Update subentry to enable show_discounted
    sub = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        entry,
        sub,
        data={**sub.data, CONF_SHOW_DISCOUNTED: True},
    )
    await hass.async_block_till_done()

    # The regular gas state should now show the discounted price (2.90)
    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.9"
    assert state.attributes.get("discounted_price") == 2.90

    # 3. Test cents_per_liter unit (CAD)
    graphql_response_cad = {
        "data": {
            "station": {
                "id": "999002",
                "name": "Cheap Station CAD",
                "phone": "(507)281-3105",
                "openStatus": "open",
                "priceUnit": "cents_per_liter",
                "currency": "CAD",
                "latitude": 41.8781,
                "longitude": -87.6298,
                "brands": [
                    {
                        "brandId": "brand_cheap",
                        "brandingType": "fuel",
                        "imageUrl": "https://images.gasbuddy.io/b/165.png",
                        "name": "Brand Cheap",
                    }
                ],
                "prices": [
                    {
                        "cash": None,
                        "credit": {
                            "nickname": "tigerdoodles",
                            "postedTime": "2026-05-19T15:02:49.375Z",
                            "price": 140.0,
                            "formattedPrice": "140.0",
                        },
                        "fuelProduct": "regular_gas",
                        "longName": "Regular",
                    }
                ],
            }
        }
    }

    mock_aioclient.clear_requests()
    mock_aioclient.get("https://www.gasbuddy.com/home", status=200, text=load_fixture("index.html"))
    mock_aioclient.post(
        "https://www.gasbuddy.com/graphql",
        status=200,
        text=json.dumps(graphql_response_cad),
    )

    sub_cad_data = {
        CONF_NAME: "Gas Station CAD",
        CONF_STATION_ID: "999002",
        CONF_INTERVAL: 3600,
        CONF_UOM: True,
        CONF_GPS: True,
        CONF_FETCH_GAS: True,
        CONF_SHOW_DISCOUNTED: True,
    }
    sub_cad = _make_station_subentry(
        data=sub_cad_data,
        title="Gas Station CAD",
        unique_id="999002",
        subentry_id="test_subentry_id_cad",
    )
    hub_cad_data = {
        CONF_NAME: "GasBuddy Hub",
        CONF_SOLVER: "",
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_BRAND_ADJUSTMENTS: {"Brand Cheap": -5.0},  # Matching by name
    }
    entry_cad = _make_hub_entry(hass, hub_data=hub_cad_data, subentries=[sub_cad])
    entry_cad.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry_cad.entry_id)
    await hass.async_block_till_done()

    # 140.0 - 5.0 = 135.0 cents/liter -> 1.35 CAD/liter
    state = hass.states.get("sensor.gas_station_cad_regular_gas")
    assert state
    assert state.state == "1.35"
    assert state.attributes.get("discounted_price") == 1.35

    # Test get_brand_adjustment coverage when data is None/empty
    coordinator = hass.data[DOMAIN][entry_cad.entry_id][COORDINATOR]
    assert coordinator.get_brand_adjustment({}) == 0.0
    original_data = coordinator.data
    coordinator.data = None
    assert coordinator.get_brand_adjustment(None) == 0.0
    coordinator.data = original_data


async def test_sensor_device_registered_under_hub_entry(hass, mock_gasbuddy):
    """Test that station devices are registered under the hub config entry.

    With the ConfigSubentry model, station devices are scoped to their subentry_id
    and live under the hub config entry. No phantom hub device or via_device nesting
    is created — HA groups them via the integration card natively.
    """
    from homeassistant.helpers import device_registry as dr  # noqa: PLC0415

    entry = _make_hub_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    # Station device must exist, scoped to the subentry
    station_device = device_registry.async_get_device(identifiers={(DOMAIN, "test_subentry_id")})
    assert station_device is not None
    assert station_device.manufacturer == "GasBuddy"

    # No phantom hub device should exist
    hub_device = device_registry.async_get_device(identifiers={(DOMAIN, "hub")})
    assert hub_device is None

    # Station device has no via_device parent
    assert station_device.via_device_id is None


async def test_sensor_setup_skips_subentry_without_coordinator(hass, mock_gasbuddy):
    """Test that async_setup_entry skips subentries that have no coordinator (sensor.py L52)."""

    # Build a hub entry with one station subentry
    sub = _make_station_subentry(subentry_id="orphan_sub", unique_id="999099")
    entry = _make_hub_entry(hass, subentries=[sub])

    # Set up the integration, but then zero out the coordinator dict before the sensor
    # platform is registered so the subentry has no coordinator
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Clear the coordinator dict and re-trigger sensor platform setup directly
    from custom_components.gasbuddy.const import COORDINATOR  # noqa: PLC0415
    from custom_components.gasbuddy.sensor import async_setup_entry  # noqa: PLC0415

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = {}  # empty — no coordinators

    sensors_added = []

    async def mock_add(entities, update_before_add=False, config_subentry_id=None):
        sensors_added.extend(entities)

    await async_setup_entry(hass, entry, mock_add)

    # Since coordinator dict is empty, the subentry is skipped — no sensors added
    assert len(sensors_added) == 0


async def test_get_setting_falls_back_to_config_data(hass, mock_gasbuddy):
    """Test _get_setting returns value from config.data when not in options or subentry data (sensor.py L146)."""

    from custom_components.gasbuddy.const import CONF_SOLVER, COORDINATOR  # noqa: PLC0415

    for solver_value in ("http://hub-solver:8191", ""):
        # Hub with CONF_SOLVER in data but not in options or subentry data
        hub_data = {**HUB_DATA, CONF_SOLVER: solver_value}
        sub = _make_station_subentry()
        entry = _make_hub_entry(hass, hub_data=hub_data, subentries=[sub])

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = next(iter(hass.data[DOMAIN][entry.entry_id][COORDINATOR].values()))
        sensor = GasBuddySensor(SENSOR_TYPES["regular_gas"], coordinator, entry, sub)

        # CONF_SOLVER is in config.data, not in options (empty) and not in subentry data
        assert sensor._get_setting(CONF_SOLVER) == solver_value  # noqa: SLF001

        # Clean up for the next loop iteration
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
