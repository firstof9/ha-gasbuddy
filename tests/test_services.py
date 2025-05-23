"""Test gasbuddy services."""

import logging

import pytest
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import ATTR_LIMIT, ATTR_POSTAL_CODE, DOMAIN
from tests.common import load_fixture

from .const import CONFIG_DATA

SERVICE_LOOKUP_GPS = "lookup_gps"
SERVICE_LOOKUP_ZIP = "lookup_zip"

pytestmark = pytest.mark.asyncio

TEST_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"


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
        entity_id, "away", {ATTR_LATITUDE: 1234, ATTR_LONGITUDE: 5678}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == 1234
    assert state.attributes[ATTR_LONGITUDE] == 5678

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
        status=400,
        body="¯\_(ツ)_/¯",
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
        assert (
            response["results"][0]["regular_gas"]["last_updated"]
            == "2024-11-18T21:58:38.859Z"
        )
        assert response["trend"]["area"] == "Arizona"
        assert response["trend"]["average_price"] == 3.33
        assert response["trend"]["lowest_price"] == 2.59

    mock_aioclient.post(
        TEST_URL,
        status=400,
        body="¯\_(ツ)_/¯",
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
