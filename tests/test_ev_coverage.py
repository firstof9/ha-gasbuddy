"""Unit tests covering EV station coordinator fallback, enrichment, and services."""
# ruff: noqa: SLF001

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from py_gasbuddy.exceptions import APIError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.config_flow import (
    GasBuddySubentryFlowHandler,
    _get_station_list,  # noqa: PLC2701
    validate_station,
)
from custom_components.gasbuddy.const import (
    ATTR_POSTAL_CODE,
    CONF_EV_CHARGING,
    CONF_FETCH_GAS,
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from custom_components.gasbuddy.coordinator import (
    GasBuddyUpdateCoordinator,
    _lon_delta,  # noqa: PLC2701
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.update_coordinator import UpdateFailed

pytestmark = pytest.mark.asyncio


async def test_coordinator_fallback_ev_matching(hass):
    """Test coordinator fallback when main price lookup fails, but ev_stations_nearby succeeds with a match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={
            CONF_EV_CHARGING: True,
        },
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    # Mock price_lookup to fail, and ev_stations_nearby to succeed with a matching ID
    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=APIError("Price lookup failed"))
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Matching Costco EV",
                    "latitude": 33.45,
                    "longitude": -112.50,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()

    assert data["station_id"] == "208656"
    assert data["name"] == "Matching Costco EV"
    assert data["latitude"] == 33.45
    assert data["longitude"] == -112.50
    assert mock_api.price_lookup.called
    assert mock_api.ev_stations_nearby.called


async def test_coordinator_fallback_ev_no_match(hass):
    """Test coordinator fallback when main price lookup fails, and ev_stations_nearby has no match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={
            CONF_EV_CHARGING: True,
        },
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=APIError("Price lookup failed"))
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "999999",  # No match
                    "name": "Other Station",
                    "latitude": 34.0,
                    "longitude": -113.0,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()

    assert data["station_id"] == "208656"
    assert data["name"] == "EV Station"
    assert data["latitude"] == hass.config.latitude
    assert data["longitude"] == hass.config.longitude


async def test_coordinator_fallback_ev_exception(hass):
    """Test coordinator fallback when both price lookup and ev_stations_nearby fail."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={
            CONF_EV_CHARGING: True,
        },
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=APIError("Price lookup failed"))
    mock_api.ev_stations_nearby = AsyncMock(side_effect=Exception("EV lookup failed"))
    coordinator._api = mock_api

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_skips_price_lookup_when_fetch_gas_disabled(hass):
    """fetch_gas=False bypasses price_lookup and falls through to EV enrichment."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            "latitude": 33.45,
            "longitude": -112.50,
        },
        options={CONF_EV_CHARGING: True, CONF_FETCH_GAS: False},
    )
    entry.add_to_hass(hass)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=AssertionError("must not be called"))
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Costco EV",
                    "level2_count": 2,
                    "dc_fast_count": 4,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()
    assert not mock_api.price_lookup.called
    assert mock_api.ev_stations_nearby.called
    assert data["station_id"] == "208656"
    assert data["ev_level2"] == 2


async def test_coordinator_raises_when_both_options_disabled(hass):
    """fetch_gas=False AND ev_charging=False → UpdateFailed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "Nothing",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={CONF_EV_CHARGING: False, CONF_FETCH_GAS: False},
    )
    entry.add_to_hass(hass)
    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_enrichment_success(hass):
    """Test coordinator success path with EV charging enabled and successful enrichment."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={
            CONF_EV_CHARGING: True,
        },
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(
        return_value={
            "station_id": "208656",
            "name": "Costco Station",
            "latitude": 33.459108,
            "longitude": -112.502745,
            "unit_of_measure": "dollars_per_gallon",
            "currency": "USD",
        }
    )
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Costco EV Station",
                    "level1_count": 0,
                    "level2_count": 2,
                    "dc_fast_count": 4,
                    "j1772_count": 2,
                    "j1772_power": 7.2,
                    "ccs_count": 4,
                    "ccs_power": 150.0,
                    "chademo_count": 0,
                    "chademo_power": 0.0,
                    "nacs_count": 0,
                    "nacs_power": 0.0,
                    "status_code": "operational",
                    "network": "Costco Network",
                    "network_web": "http://costco.com",
                    "pricing": "Free for members",
                    "access_hours": "24/7",
                    "access_code": "None",
                    "cards_accepted": "A D Debit M V",
                    "date_last_confirmed": "2026-05-18",
                    "street_address": "1101 N Verrado Way",
                    "city": "Buckeye",
                    "state": "AZ",
                    "distance_miles": 1.5,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()

    assert data["ev_level1"] == 0
    assert data["ev_level2"] == 2
    assert data["ev_dc_fast"] == 4
    assert data["ev_j1772"] == 2
    assert data["ev_j1772_power"] == 7.2
    assert data["ev_ccs"] == 4
    assert data["ev_ccs_power"] == 150.0
    assert data["ev_status"] == "operational"
    assert data["ev_network"] == "Costco Network"
    assert data["ev_cards_accepted"] == "American Express, Discover, Debit Card, Mastercard, Visa"
    assert data["ev_station_address"] == "1101 N Verrado Way, Buckeye, AZ"
    assert data["ev_distance_miles"] == 1.5


async def test_coordinator_enrichment_exception_logged(hass, caplog):
    """Test coordinator enrichment handles exception gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={
            CONF_EV_CHARGING: True,
        },
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(
        return_value={
            "station_id": "208656",
            "name": "Costco Station",
            "latitude": 33.459108,
            "longitude": -112.502745,
            "unit_of_measure": "dollars_per_gallon",
            "currency": "USD",
        }
    )
    mock_api.ev_stations_nearby = AsyncMock(side_effect=Exception("GraphQLTimeout"))
    coordinator._api = mock_api

    with caplog.at_level(logging.WARNING):
        data = await coordinator._async_update_data()

    assert data["station_id"] == "208656"
    assert "Failed to fetch EV station data: GraphQLTimeout" in caplog.text


async def test_services_ev_lookup_gps(hass, mock_gasbuddy):
    """Test ev_lookup_gps service under different entity coordinate scenarios."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            CONF_GPS: True,
            CONF_NAME: DEFAULT_NAME,
            CONF_STATION_ID: "208656",
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 1. Entity with valid coordinates
    entity_valid = "device_tracker.valid_gps"
    hass.states.async_set(
        entity_valid, "home", {ATTR_LATITUDE: 33.459108, ATTR_LONGITUDE: -112.502745}, True
    )

    # 2. Entity missing coordinates
    entity_no_coords = "device_tracker.no_coords"
    hass.states.async_set(entity_no_coords, "home", {}, True)

    # 3. Entity that causes exception in API lookup
    entity_exception = "device_tracker.exception_trigger"
    hass.states.async_set(
        entity_exception, "home", {ATTR_LATITUDE: 34.0, ATTR_LONGITUDE: -113.0}, True
    )

    await hass.async_block_till_done()

    # Patch the GasBuddy client used inside services.py
    with (
        patch("custom_components.gasbuddy.services.GasBuddy.ev_stations_nearby") as mock_ev_api,
    ):

        def ev_side_effect(lat, lon, radius=None, limit=None):
            if lat == 33.459108:
                return {"stations": [{"station_id": "123", "name": "Test EV Station"}]}
            raise RuntimeError("Simulated service exception")

        mock_ev_api.side_effect = ev_side_effect

        response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_gps",
            {ATTR_ENTITY_ID: [entity_valid, entity_no_coords, entity_exception]},
            blocking=True,
            return_response=True,
        )

        # Check results
        assert entity_valid in response
        assert response[entity_valid] == [{"station_id": "123", "name": "Test EV Station"}]

        assert entity_no_coords in response
        assert response[entity_no_coords] == []

        assert entity_exception in response
        assert response[entity_exception] == []


async def test_services_ev_lookup_zip_success(hass, mock_gasbuddy):
    """Test ev_lookup_zip service with successful coordinates and station lookup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            CONF_GPS: True,
            CONF_NAME: DEFAULT_NAME,
            CONF_STATION_ID: "208656",
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("custom_components.gasbuddy.services.GasBuddy.price_lookup_service") as mock_lookup,
        patch("custom_components.gasbuddy.services.GasBuddy.ev_stations_nearby") as mock_ev,
    ):
        mock_lookup.return_value = {"results": [{"latitude": 33.45, "longitude": -112.50}]}
        mock_ev.return_value = {"stations": [{"station_id": "999", "name": "Zip EV Station"}]}

        response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_zip",
            {ATTR_POSTAL_CODE: "85326"},
            blocking=True,
            return_response=True,
        )

        assert response["stations"] == [{"station_id": "999", "name": "Zip EV Station"}]
        assert "error" not in response


async def test_services_ev_lookup_zip_missing_coords(hass, mock_gasbuddy):
    """Test ev_lookup_zip service when price_lookup_service succeeds but coordinates are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            CONF_GPS: True,
            CONF_NAME: DEFAULT_NAME,
            CONF_STATION_ID: "208656",
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("custom_components.gasbuddy.services.GasBuddy.price_lookup_service") as mock_lookup,
    ):
        # Coordinates missing in the return payload
        mock_lookup.return_value = {"results": [{"latitude": None, "longitude": None}]}

        response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_zip",
            {ATTR_POSTAL_CODE: "85326"},
            blocking=True,
            return_response=True,
        )

        assert response["stations"] == []
        assert response["error"] == "Location coordinates not found for zip code"


async def test_services_ev_lookup_zip_exception(hass, mock_gasbuddy):
    """Test ev_lookup_zip service when price_lookup_service raises an exception."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            CONF_GPS: True,
            CONF_NAME: DEFAULT_NAME,
            CONF_STATION_ID: "208656",
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("custom_components.gasbuddy.services.GasBuddy.price_lookup_service") as mock_lookup,
    ):
        mock_lookup.side_effect = Exception("API down")

        response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_zip",
            {ATTR_POSTAL_CODE: "85326"},
            blocking=True,
            return_response=True,
        )

        assert response["stations"] == []
        assert response["error"] == "API down"


async def test_services_ev_lookup_optional_params(hass, mock_gasbuddy):
    """Test ev_lookup_gps and ev_lookup_zip services with all optional parameters (limit, radius, solver)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            CONF_GPS: True,
            CONF_NAME: DEFAULT_NAME,
            CONF_STATION_ID: "208656",
            CONF_INTERVAL: 3600,
            CONF_UOM: True,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_valid = "device_tracker.valid_gps"
    hass.states.async_set(
        entity_valid, "home", {ATTR_LATITUDE: 33.459108, ATTR_LONGITUDE: -112.502745}, True
    )
    await hass.async_block_till_done()

    with patch("custom_components.gasbuddy.services.GasBuddy") as mock_gb_class:
        mock_lookup = AsyncMock(
            return_value={"results": [{"latitude": 33.45, "longitude": -112.50}]}
        )
        mock_gb_class.return_value.price_lookup_service = mock_lookup
        mock_ev = AsyncMock(
            return_value={"stations": [{"station_id": "999", "name": "Zip EV Station"}]}
        )
        mock_gb_class.return_value.ev_stations_nearby = mock_ev

        # 1. Test GPS EV service with optional parameters
        gps_response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_gps",
            {
                ATTR_ENTITY_ID: [entity_valid],
                "limit": 10,
                "radius": 50,
                "solver": "http://custom-solver.local",
            },
            blocking=True,
            return_response=True,
        )
        assert entity_valid in gps_response
        assert gps_response[entity_valid] == [{"station_id": "999", "name": "Zip EV Station"}]

        # 2. Test ZIP EV service with optional parameters
        zip_response = await hass.services.async_call(
            DOMAIN,
            "ev_lookup_zip",
            {
                ATTR_POSTAL_CODE: "85326",
                "limit": 10,
                "radius": 50,
                "solver": "http://custom-solver.local",
            },
            blocking=True,
            return_response=True,
        )
        assert zip_response["stations"] == [{"station_id": "999", "name": "Zip EV Station"}]

        # Verify that the optional parameters were correctly forwarded to the API client methods
        assert any(
            call.kwargs.get("limit") == 10 and call.kwargs.get("radius") == 50
            for call in mock_ev.call_args_list
        )
        # Verify that the custom solver URL was correctly passed to the GasBuddy constructor
        assert any(
            call.kwargs.get("solver_url") == "http://custom-solver.local"
            for call in mock_gb_class.call_args_list
        )


async def test_validate_station_ev(hass):
    """Test validate_station when price_lookup fails but station exists in nearby EV stations."""

    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
            side_effect=APIError("Fail"),
        ),
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.ev_stations_nearby"
        ) as mock_ev,
    ):
        mock_ev.return_value = {
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Costco EV",
                }
            ]
        }
        result = await validate_station(hass, station="208656")
        assert result == {
            "type": "ev",
            "latitude": None,
            "longitude": None,
        }


async def test_get_station_list_postal_coordinates_and_ev(hass):
    """Test direct _get_station_list call resolving postal coordinates and merging EV stations."""

    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.location_search"
        ) as mock_loc,
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup_service"
        ) as mock_price_srv,
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.ev_stations_nearby"
        ) as mock_ev,
    ):
        mock_loc.return_value = {
            "results": [
                {
                    "station_id": "1",
                    "name": "Gas Station 1",
                    "address": {"line1": "123 Main St"},
                }
            ]
        }
        mock_price_srv.return_value = {
            "results": [
                {
                    "latitude": 33.45,
                    "longitude": -112.50,
                }
            ]
        }
        mock_ev.return_value = {
            "stations": [
                {
                    "station_id": "ev_1",
                    "name": "EV Station 1",
                    "street_address": "456 Charge Rd",
                }
            ]
        }

        stations = await _get_station_list(hass, {CONF_POSTAL: "85326"})
        assert stations == {
            "1": "Gas Station 1 @ 123 Main St",
            "ev_1": "EV Station 1 @ 456 Charge Rd [EV]",
        }


async def test_config_flow_ev_charging_flag(hass):
    """Test ConfigFlow sets ev_charging to True when station ends with [EV]."""
    flow = GasBuddySubentryFlowHandler()
    flow.hass = hass
    # async_set_unique_id mutates self.context; when constructing the flow
    # directly (not via the flow manager) the default context is a
    # read-only mappingproxy, so replace it with a real dict.
    flow.context = {"source": "user"}
    flow._station_list = {"208656": "Costco [EV]"}
    flow._data = {CONF_NAME: "Costco Station", CONF_STATION_ID: "208656"}
    flow._get_entry = MagicMock(return_value=MockConfigEntry())

    # 1. Test async_step_home2
    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "ev", "latitude": 33.45, "longitude": -112.50},
        ),
        patch("custom_components.gasbuddy.async_setup_entry", return_value=True),
    ):
        result = await flow.async_step_home2({
            CONF_STATION_ID: "208656",
            CONF_NAME: "Costco Station",
        })
        assert result["type"] == "create_entry"
        assert result["data"][CONF_EV_CHARGING] is True
        assert flow._data["latitude"] == 33.45
        assert flow._data["longitude"] == -112.50

    # 2. Test async_step_station_list
    flow._data = {CONF_POSTAL: "85326", CONF_NAME: "Costco Station", CONF_STATION_ID: "208656"}

    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "ev", "latitude": 33.45, "longitude": -112.50},
        ),
        patch("custom_components.gasbuddy.async_setup_entry", return_value=True),
    ):
        result = await flow.async_step_station_list({
            CONF_STATION_ID: "208656",
            CONF_NAME: "Costco Station",
        })
        assert result["type"] == "create_entry"
        assert result["data"][CONF_EV_CHARGING] is True
        assert flow._data["latitude"] == 33.45
        assert flow._data["longitude"] == -112.50


async def test_ev_station_id_collision_coordinator(hass) -> None:
    """Test coordinator handles ID collision by raising APIError and falling back to EV search."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Collision Station",
        data={
            CONF_NAME: "Collision Station",
            CONF_STATION_ID: "8861",
            "latitude": 44.0,
            "longitude": -92.0,
        },
        options={CONF_EV_CHARGING: True},
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    mock_api = MagicMock()

    # Gas lookup succeeds but returns distant coordinates
    mock_api.price_lookup = AsyncMock(
        return_value={
            "station_id": "8861",
            "name": "Wrong Station",
            "latitude": 47.0,
            "longitude": -121.0,
        }
    )

    # Fallback EV search succeeds with correct nearby coordinates
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "8861",
                    "name": "Correct EV Station",
                    "latitude": 44.0,
                    "longitude": -92.0,
                    "distance_miles": 0.0,
                    "level2_count": 2,
                }
            ]
        }
    )

    coordinator._api = mock_api
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert mock_api.price_lookup.called
    assert mock_api.ev_stations_nearby.called
    assert coordinator.data["ev_level2"] == 2
    assert "regular_gas" not in coordinator.data


async def test_validate_station_id_collision(hass) -> None:
    """Test validate_station handles ID collision correctly."""

    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
            new_callable=AsyncMock,
        ) as mock_price_lookup,
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.ev_stations_nearby",
            new_callable=AsyncMock,
        ) as mock_ev_search,
    ):
        # Distant gas station
        mock_price_lookup.return_value = {
            "latitude": 47.0,
            "longitude": -121.0,
        }
        # Correct EV station nearby
        mock_ev_search.return_value = {
            "stations": [{"station_id": "8861", "latitude": 44.0, "longitude": -92.0}]
        }

        result = await validate_station(hass, station="8861", solver=None, lat=44.0, lon=-92.0)

        assert isinstance(result, dict)
        assert result["type"] == "ev"
        assert result["latitude"] == 44.0


async def test_coordinator_fallback_preserves_unit_and_currency(hass):
    """EV fallback carries unit_of_measure/currency from the last good poll, not hardcoded USD/gallon."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={CONF_EV_CHARGING: True},
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)
    # Simulate a previous successful poll of a Canadian station.
    coordinator._data = {"unit_of_measure": "cents_per_liter", "currency": "CAD"}

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=APIError("Price lookup failed"))
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Matching Costco EV",
                    "latitude": 33.45,
                    "longitude": -112.50,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()

    assert data["unit_of_measure"] == "cents_per_liter"
    assert data["currency"] == "CAD"


async def test_coordinator_fallback_omits_unit_when_unknown(hass):
    """On the first poll (no prior data) the fallback omits unit/currency rather than guessing USD/gallon."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATION_ID: "208656",
            CONF_NAME: "EV Station",
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        options={CONF_EV_CHARGING: True},
    )
    entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, entry)

    mock_api = MagicMock()
    mock_api.price_lookup = AsyncMock(side_effect=APIError("Price lookup failed"))
    mock_api.ev_stations_nearby = AsyncMock(
        return_value={
            "stations": [
                {
                    "station_id": "208656",
                    "name": "Matching Costco EV",
                    "latitude": 33.45,
                    "longitude": -112.50,
                }
            ]
        }
    )
    coordinator._api = mock_api

    data = await coordinator._async_update_data()

    assert "unit_of_measure" not in data
    assert "currency" not in data


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (10.0, 11.0, 1.0),
        (179.9, -179.9, 0.2),
        (-179.9, 179.9, 0.2),
    ],
)
async def test_coordinator_lon_delta(a, b, expected):
    """Coordinator longitude delta wraps across the antimeridian."""
    assert _lon_delta(a, b) == pytest.approx(expected)
