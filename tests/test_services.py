"""Test gasbuddy services."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    ATTR_DEVICE_ID,
    ATTR_LIMIT,
    ATTR_POSTAL_CODE,
    ATTR_SOLVER,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from tests.common import load_fixture

from .const import CONFIG_DATA

SERVICE_LOOKUP_GPS = "lookup_gps"
SERVICE_LOOKUP_ZIP = "lookup_zip"
SERVICE_CLEAR_CACHE = "clear_cache"

pytestmark = pytest.mark.asyncio

TEST_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"


async def test_lookup_gps(
    hass,
    mock_gasbuddy,
    mock_aioclient,
    caplog,
):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("results.json"),
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.fake_gps"
    # Set our fake device_tracker state/attributes
    hass.states.async_set(
        entity_id, "away", {ATTR_LATITUDE: 33.459108, ATTR_LONGITUDE: -112.502745}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == 33.459108
    assert state.attributes[ATTR_LONGITUDE] == -112.502745

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )

        assert response[entity_id]["results"][0]["regular_gas"]["price"] == 3.28
        assert response[entity_id]["results"][0]["regular_gas"]["credit"] == "fred1129"
        assert (
            response[entity_id]["results"][0]["regular_gas"]["last_updated"]
            == "2024-11-18T21:58:38.859Z"
        )

        mock_aioclient.post(
            TEST_URL,
            status=200,
            body=load_fixture("results.json"),
        )

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {ATTR_ENTITY_ID: entity_id, ATTR_LIMIT: 10},
            blocking=True,
            return_response=True,
        )

        assert len(response[entity_id]["results"]) == 10

        mock_aioclient.post(
            TEST_URL,
            status=200,
            body=load_fixture("results.json"),
        )

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {ATTR_ENTITY_ID: entity_id, ATTR_LIMIT: 10, ATTR_SOLVER: SOLVER_URL},
            blocking=True,
            return_response=True,
        )

        assert len(response[entity_id]["results"]) == 10

    mock_aioclient.post(
        TEST_URL,
        status=400,
        body=r"¯\_(ツ)_/¯",
    )

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )
        assert "Error checking prices:" in caplog.text


async def test_lookup_zip(
    hass,
    mock_gasbuddy,
    mock_aioclient,
    caplog,
):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("results.json"),
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            {ATTR_POSTAL_CODE: 12345, ATTR_LIMIT: 10},
            blocking=True,
            return_response=True,
        )

        assert response["results"][0]["regular_gas"]["price"] == 3.28
        assert response["results"][0]["regular_gas"]["credit"] == "fred1129"
        assert response["results"][0]["regular_gas"]["last_updated"] == "2024-11-18T21:58:38.859Z"
        assert response["trend"][0]["area"] == "Arizona"
        assert response["trend"][0]["average_price"] == 3.33
        assert response["trend"][0]["lowest_price"] == 2.59
        assert response["trend"][1]["area"] == "United States"
        assert response["trend"][1]["average_price"] == 3.11
        assert response["trend"][1]["lowest_price"] == 0

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("results.json"),
    )

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            {ATTR_POSTAL_CODE: 12345, ATTR_LIMIT: 10, ATTR_SOLVER: SOLVER_URL},
            blocking=True,
            return_response=True,
        )

        assert response["results"][0]["regular_gas"]["price"] == 3.28
        assert response["results"][0]["regular_gas"]["credit"] == "fred1129"
        assert response["results"][0]["regular_gas"]["last_updated"] == "2024-11-18T21:58:38.859Z"
        assert response["trend"][0]["area"] == "Arizona"
        assert response["trend"][0]["average_price"] == 3.33
        assert response["trend"][0]["lowest_price"] == 2.59
        assert response["trend"][1]["area"] == "United States"
        assert response["trend"][1]["average_price"] == 3.11
        assert response["trend"][1]["lowest_price"] == 0

    mock_aioclient.post(
        TEST_URL,
        status=400,
        body=r"¯\_(ツ)_/¯",
    )

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            {ATTR_POSTAL_CODE: 12345},
            blocking=True,
            return_response=True,
        )
        assert "Error checking prices:" in caplog.text


async def test_clear_cache(
    hass,
    mock_gasbuddy,
    mock_aioclient,
    entity_registry: er.EntityRegistry,
    caplog,
):
    """Test clear cache service."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("results.json"),
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level(logging.DEBUG):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_ZIP,
            {ATTR_POSTAL_CODE: 12345, ATTR_LIMIT: 10},
            blocking=True,
            return_response=True,
        )

        assert response["results"][0]["regular_gas"]["price"] == 3.28
        assert response["results"][0]["regular_gas"]["credit"] == "fred1129"
        assert response["results"][0]["regular_gas"]["last_updated"] == "2024-11-18T21:58:38.859Z"
        assert response["trend"][0]["area"] == "Arizona"
        assert response["trend"][0]["average_price"] == 3.33
        assert response["trend"][0]["lowest_price"] == 2.59
        assert response["trend"][1]["area"] == "United States"
        assert response["trend"][1]["average_price"] == 3.11
        assert response["trend"][1]["lowest_price"] == 0

    entry = entity_registry.async_get("sensor.gas_station_regular_gas")
    assert entry
    assert entry.device_id

    with caplog.at_level(logging.DEBUG):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            {ATTR_DEVICE_ID: entry.device_id},
            blocking=True,
            return_response=False,
        )
        assert "Cache file cleared." in caplog.text

        with pytest.raises(ValueError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLEAR_CACHE,
                {ATTR_DEVICE_ID: "ADSF1234234ADFH"},
                blocking=True,
                return_response=False,
            )
        assert "Device_entry: None" in caplog.text


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


async def test_lookup_gps_invalid_solver(hass, mock_gasbuddy, mock_aioclient):
    """lookup_gps raises ServiceValidationError for invalid solver URL (services.py line 53)."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Invalid FlareSolverr URL"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {
                ATTR_ENTITY_ID: "sensor.gas_station_regular_gas",
                ATTR_LIMIT: 5,
                ATTR_SOLVER: "not-a-valid-url",
            },
            blocking=True,
            return_response=True,
        )


async def test_clear_cache_no_config_entry(hass, mock_gasbuddy, mock_aioclient, caplog):
    """clear_cache raises ValueError when device has no config entry (services.py line 295)."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device = MagicMock()
    mock_device.config_entries = set()

    with patch("custom_components.gasbuddy.services.dr.async_get") as mock_reg:
        mock_reg.return_value.async_get.return_value = mock_device
        with pytest.raises(ValueError, match="No config entry found"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLEAR_CACHE,
                {ATTR_DEVICE_ID: "fake_device_id"},
                blocking=True,
                return_response=False,
            )


async def test_lookup_gps_missing_coordinates(hass, mock_gasbuddy, mock_aioclient, caplog):
    """lookup_gps warns and returns an empty result for an entity without coordinates."""
    entry = MockConfigEntry(domain=DOMAIN, title="Gas Station", data=CONFIG_DATA)
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("results.json"))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.no_coords"
    hass.states.async_set(entity_id, "home", {})
    await hass.async_block_till_done()

    with caplog.at_level(logging.WARNING):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP_GPS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )

    assert response[entity_id] == {}
    assert "lacks latitude/longitude coordinates" in caplog.text
