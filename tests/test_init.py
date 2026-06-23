"""Test gasbuddy setup process."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy import async_remove_config_entry_device
from custom_components.gasbuddy.const import (
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_SOLVER,
    CONF_UOM,
    CONFIG_VER,
    DOMAIN,
)
from custom_components.gasbuddy.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.common import load_fixture
from tests.const import CONFIG_DATA, CONFIG_DATA_V1

pytestmark = pytest.mark.asyncio

BASE_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"


async def test_setup_and_unload_entry(hass, mock_gasbuddy):
    """Test setup_entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


async def test_setup_and_unload_entry_v1(hass, mock_gasbuddy):
    """Test setup_entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA_V1, version=1)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 8
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


async def test_setup_with_error(hass, mock_aioclient):
    """Test server side errors on start up."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("server_error.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)

    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_migrate_entry(hass, mock_gasbuddy):
    """Test entry migration."""
    # Create an entry with version 1 data
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA_V1, version=1)

    entry.add_to_hass(hass)

    # Setup the entry - this triggers the migration
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify the version is updated to current
    assert entry.version == CONFIG_VER

    # Verify new keys are added
    assert entry.data[CONF_UOM] is True
    assert entry.data[CONF_GPS] is True
    assert entry.data[CONF_SOLVER] is None
    assert entry.data[CONF_EXCLUDE_BRANDS] == []
    assert entry.data[CONF_INCLUDE_BRANDS] == []
    assert entry.data[CONF_EXCLUDE_STATIONS] == []
    assert entry.data[CONF_INCLUDE_STATIONS] == []


async def test_migrate_entry_advances_version_without_data_change(hass, mock_gasbuddy):
    """Migration must advance the version even when no data keys need adding.

    CONFIG_DATA already contains every key the migration steps would add, so
    the data dict is unchanged. The entry version still has to move to
    CONFIG_VER, otherwise HA re-runs the migration on every startup.
    """
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == CONFIG_VER


async def test_remove_config_entry_device(hass, integration):
    """Test async_remove_config_entry_device."""

    assert await async_remove_config_entry_device(hass, integration, None) is True


async def test_options_reload(hass, mock_gasbuddy):
    """Test integration reloads on option changes."""
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload:
        hass.config_entries.async_update_entry(entry, options={**entry.options, "interval": 1200})
        await hass.async_block_till_done()
        assert mock_reload.called


async def test_sanity_defaults_add_fetch_gas(hass, mock_gasbuddy):
    """async_setup_entry should populate CONF_FETCH_GAS when missing from options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data=CONFIG_DATA,
        options={},  # intentionally empty — simulates old entry missing CONF_FETCH_GAS
        version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.options.get(CONF_FETCH_GAS) is True


async def test_config_diagnostics_includes_coordinator(hass, integration):
    """Config-level diagnostics should include coordinator data alongside config."""
    result = await async_get_config_entry_diagnostics(hass, integration)
    assert "config" in result
    assert "coordinator_data" in result
    assert "last_updated" in result["coordinator_data"]


async def test_service_unregistration_on_unload(hass, mock_gasbuddy):
    """Test services are unregistered on unload."""
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "lookup_gps")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "lookup_gps")
