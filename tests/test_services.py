"""Test gasbuddy services."""

import logging

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
from homeassistant.helpers import device_registry as dr, entity_registry as er
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


async def _setup_clear_cache_entry(hass, mock_aioclient):
    """Set up a config entry so its coordinator lives in hass.data."""
    entry = MockConfigEntry(domain=DOMAIN, title="Gas Station", data=CONFIG_DATA)
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("results.json"))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_clear_cache_connections_fallback(hass, mock_gasbuddy, mock_aioclient):
    """clear_cache resolves the config id via legacy `connections` when no identifier matches."""
    entry = await _setup_clear_cache_entry(hass, mock_aioclient)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    # Drop the domain identifier so resolution must fall back to connections,
    # mirroring a device registered by an older release.
    device_registry.async_update_device(
        device.id, new_identifiers={("gasbuddy_legacy", entry.entry_id)}
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        {ATTR_DEVICE_ID: device.id},
        blocking=True,
        return_response=False,
    )


async def test_clear_cache_no_domain_match(hass, mock_gasbuddy, mock_aioclient):
    """clear_cache raises when the device belongs to no gasbuddy config entry."""
    entry = await _setup_clear_cache_entry(hass, mock_aioclient)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("other_integration", "abc")}
    )

    with pytest.raises(ValueError, match="not registered against"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
            return_response=False,
        )


async def test_clear_cache_unknown_config_entry(hass, mock_gasbuddy, mock_aioclient):
    """clear_cache raises when the resolved config id has no loaded entry."""
    entry = await _setup_clear_cache_entry(hass, mock_aioclient)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "missing-config-id")}
    )

    with pytest.raises(ValueError, match="unknown config entry"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
            return_response=False,
        )
