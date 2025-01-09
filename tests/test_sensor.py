"""Test gasbuddy sensors."""

from datetime import datetime
import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import DOMAIN

from .const import CONFIG_DATA, CONFIG_DATA_NO_UOM

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

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "2.95"
    assert state.attributes["unit_of_measurement"] == "USD/gallon"
    assert state.attributes[ATTR_LATITUDE] == 33.459108
    assert state.attributes[ATTR_LONGITUDE] == -112.502745
    assert (
        state.attributes[ATTR_ENTITY_PICTURE] == "https://images.gasbuddy.io/b/122.png"
    )
    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state
    assert state.state == "unavailable"
    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "unknown"

    # enable disabled sensor
    entity_id = "sensor.gas_station_premium_gas_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "3.35"

    state = hass.states.get("sensor.gas_station_last_updated")
    assert state
    assert state.state == "2025-01-09T16:12:51+00:00"   


async def test_sensors_no_uom(hass, mock_gasbuddy, entity_registry: er.EntityRegistry):
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
    assert state.attributes[ATTR_LATITUDE] == 33.459108
    assert state.attributes[ATTR_LONGITUDE] == -112.502745
    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state
    assert state.state == "unavailable"
    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "unknown"

    # enable disabled sensor
    entity_id = "sensor.gas_station_e85_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"


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

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert DOMAIN in hass.config.components

    state = hass.states.get("sensor.gas_station_regular_gas")
    assert state
    assert state.state == "1.439"
    assert state.attributes["unit_of_measurement"] == "CAD/liter"
    assert state.attributes[ATTR_LATITUDE] == 33.459108
    assert state.attributes[ATTR_LONGITUDE] == -112.502745
    assert ATTR_ENTITY_PICTURE not in state.attributes
    state = hass.states.get("sensor.gas_station_midgrade_gas")
    assert state
    assert state.state == "unavailable"
    state = hass.states.get("sensor.gas_station_premium_gas")
    assert state
    assert state.state == "1.531"

    # enable disabled sensor
    entity_id = "sensor.gas_station_premium_gas_cash"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    assert await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1.452"
