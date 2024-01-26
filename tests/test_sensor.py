"""Test gasbuddy sensors."""

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import DOMAIN

from .const import CONFIG_DATA, CONFIG_DATA_NO_UOM

pytestmark = pytest.mark.asyncio


async def test_sensors(hass, mock_gasbuddy):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.95"
    assert state.attributes["unit_of_measurement"] == "USD/gallon"
    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state
    assert state.state == "unavailable"
    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "3.45"


async def test_sensors_no_uom(hass, mock_gasbuddy):
    """Test setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA_NO_UOM,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.95"
    assert state.attributes["unit_of_measurement"] == "USD"
    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state
    assert state.state == "unavailable"
    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "3.45"
