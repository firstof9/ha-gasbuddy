"""Test gasbuddy sensors."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_EV_CHARGING,
    CONF_FETCH_GAS,
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
)
from custom_components.gasbuddy.sensor import GasBuddySensor
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import as_utc, parse_datetime
from tests.common import load_fixture

from .const import (
    CONFIG_DATA,
    CONFIG_DATA_CHEAPEST,
    CONFIG_DATA_NO_UOM,
    COORDINATOR_DATA,
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

    mock_aioclient.get("https://www.gasbuddy.com/home", status=200, body=load_fixture("index.html"))
    mock_aioclient.post(
        "https://www.gasbuddy.com/graphql", status=200, body=load_fixture("station.json")
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
    assert attrs.get("address") == "100 Test Blvd, Springfield, IL"
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
    import copy  # noqa: PLC0415

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
    from custom_components.gasbuddy.const import CONF_POSTAL  # noqa: PLC0415

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
    from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: PLC0415

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
    from py_gasbuddy.exceptions import APIError  # noqa: PLC0415

    from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: PLC0415

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
    from custom_components.gasbuddy.const import CONF_PRICE_TYPE  # noqa: PLC0415

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
    from custom_components.gasbuddy.const import CONF_PRICE_TYPE  # noqa: PLC0415

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
    from custom_components.gasbuddy.const import CONF_PRICE_TYPE  # noqa: PLC0415

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
    from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: PLC0415

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
