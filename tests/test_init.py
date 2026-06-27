"""Test gasbuddy setup process."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy import async_remove_config_entry_device
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
    CONF_SOLVER,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    DOMAIN,
)
from custom_components.gasbuddy.coordinator import GasBuddyUpdateCoordinator
from custom_components.gasbuddy.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntries
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


async def test_virtual_hub_setup_and_migration(hass):
    """Test setting up Virtual Hub entry automatically migrates options from existing entries."""
    station_entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data={
            **CONFIG_DATA,
            CONF_SOLVER: "http://flaresolverr:8191",
            CONF_BRAND_ADJUSTMENTS: {"brand_a": -0.05},
        },
        options={
            CONF_TIMEOUT: 5000,
        },
        version=2,
    )
    station_entry.add_to_hass(hass)

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={},
        version=2,
    )
    hub_entry.add_to_hass(hass)

    # Setup the hub entry - triggers migration
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that the hub entry imported the settings
    assert hub_entry.data[CONF_SOLVER] == "http://flaresolverr:8191"
    assert hub_entry.data[CONF_BRAND_ADJUSTMENTS] == {"brand_a": -0.05}
    assert hub_entry.data[CONF_TIMEOUT] == 5000

    # Verify the station entry was cleaned up
    assert CONF_SOLVER not in station_entry.data
    assert CONF_BRAND_ADJUSTMENTS not in station_entry.data
    assert CONF_TIMEOUT not in station_entry.options


async def test_virtual_hub_migration_edge_cases(hass):
    """Test Virtual Hub migration edge cases for full coverage."""
    # 1. Test entry with no settings (covers line 56 - continue on missing setting)
    empty_entry = MockConfigEntry(
        domain=DOMAIN,
        title="empty_station",
        data={},
        options={},
        version=2,
    )
    empty_entry.add_to_hass(hass)

    # 2. Test conflict in brand adjustments (covers line 66 - conflict warning)
    conflicting_entry = MockConfigEntry(
        domain=DOMAIN,
        title="conflicting_station",
        data={
            CONF_BRAND_ADJUSTMENTS: {"brand_a": -0.10},
        },
        options={},
        version=2,
    )
    conflicting_entry.add_to_hass(hass)

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={
            CONF_BRAND_ADJUSTMENTS: {"brand_a": -0.05},
        },
        options={},
        version=2,
    )
    hub_entry.add_to_hass(hass)

    # Setup the hub entry - triggers migration and logs conflict warning
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # 3. Test exception in migration update (covers lines 124-125)
    # Remove previous hub and stations first
    await hass.config_entries.async_remove(hub_entry.entry_id)
    await hass.config_entries.async_remove(empty_entry.entry_id)
    await hass.config_entries.async_remove(conflicting_entry.entry_id)
    await hass.async_block_till_done()

    # Create a fresh station entry with settings that should be preserved on migration failure
    station_entry_err = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station_err",
        data={
            **CONFIG_DATA,
            CONF_SOLVER: "http://flaresolverr:8191",
            CONF_BRAND_ADJUSTMENTS: {"Shell": -0.05},
        },
        options={
            CONF_TIMEOUT: 5000,
        },
        version=9,
    )
    station_entry_err.add_to_hass(hass)

    hub_entry_err = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub Err",
        unique_id="hub",
        data={},
        options={},
        version=9,
    )
    hub_entry_err.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_update_entry",
        side_effect=Exception("Update entry failed"),
    ):
        assert await hass.config_entries.async_setup(hub_entry_err.entry_id)
        await hass.async_block_till_done()

    # Verify that the station entry data was NOT cleaned up
    assert station_entry_err.data[CONF_SOLVER] == "http://flaresolverr:8191"
    assert station_entry_err.data[CONF_BRAND_ADJUSTMENTS] == {"Shell": -0.05}
    assert station_entry_err.options[CONF_TIMEOUT] == 5000


async def test_coordinator_get_hub_setting_from_options(hass):
    """Test that _get_hub_setting retrieves value from hub options (covers line 119 in coordinator.py)."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={
            CONF_SOLVER: "http://options-solver",
            CONF_TIMEOUT: 0,
        },
        version=9,
    )
    hub_entry.add_to_hass(hass)

    station_entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data=CONFIG_DATA,
        options={},
        version=9,
    )
    station_entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, station_entry)
    assert coordinator._get_hub_setting(CONF_SOLVER) == "http://options-solver"  # noqa: SLF001
    assert coordinator._get_hub_setting(CONF_TIMEOUT, 30) == 0  # noqa: SLF001


async def test_migration_phase3_failure_preserves_stations(hass, mock_gasbuddy):
    """Test that Phase 3 failure leaves stations with redundant data and sets migrated flag."""
    station_entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data={
            **CONFIG_DATA,
            CONF_SOLVER: "http://flaresolverr:8191",
        },
        options={
            CONF_TIMEOUT: 5000,
            CONF_UOM: True,
            CONF_GPS: True,
            CONF_INTERVAL: 3600,
            CONF_EV_CHARGING: False,
            CONF_FETCH_GAS: True,
        },
        version=9,
    )
    station_entry.add_to_hass(hass)

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={},
        version=9,
    )
    hub_entry.add_to_hass(hass)

    original_update = ConfigEntries.async_update_entry

    def side_effect(self, config_entry, **kwargs):
        if config_entry.unique_id != "hub":  # Phase 3 (station cleanup) fails
            raise RuntimeError("Update failed")
        return original_update(self, config_entry, **kwargs)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_update_entry",
        autospec=True,
        side_effect=side_effect,
    ):
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

    # Hub has the data (Phase 2 succeeded)
    assert hub_entry.data.get("migrated") is True
    assert hub_entry.data.get("stations_cleaned") is not True
    # Station still has redundant data (Phase 3 failed)
    assert station_entry.data.get(CONF_SOLVER) == "http://flaresolverr:8191"


async def test_coordinator_get_hub_setting_dynamic_and_none_fallback(hass):
    """Test that coordinator settings lookup handles recreated hub and fallback defaults on None values."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={
            CONF_SOLVER: "http://solver-v1",
        },
        version=9,
    )
    hub_entry.add_to_hass(hass)

    station_entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data={
            **CONFIG_DATA,
            CONF_SOLVER: None,  # Test that None in data triggers fallback to default
        },
        options={},
        version=9,
    )
    station_entry.add_to_hass(hass)

    coordinator = GasBuddyUpdateCoordinator(hass, station_entry)
    assert coordinator._get_hub_setting(CONF_SOLVER) == "http://solver-v1"  # noqa: SLF001

    # Remove the old hub and add a new one (simulating hub deletion and recreation)
    await hass.config_entries.async_remove(hub_entry.entry_id)
    await hass.async_block_till_done()

    hub_entry_v2 = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub V2",
        unique_id="hub",
        data={},
        options={
            CONF_SOLVER: "http://solver-v2",
        },
        version=9,
    )
    hub_entry_v2.add_to_hass(hass)

    # Verify that the coordinator dynamically picks up the new hub settings
    assert coordinator._get_hub_setting(CONF_SOLVER) == "http://solver-v2"  # noqa: SLF001

    # Remove the hub entirely and assert that local data None value correctly falls back to default
    await hass.config_entries.async_remove(hub_entry_v2.entry_id)
    await hass.async_block_till_done()
    assert (
        coordinator._get_hub_setting(CONF_SOLVER, "http://default-solver")  # noqa: SLF001
        == "http://default-solver"
    )
