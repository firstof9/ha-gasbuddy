"""Test gasbuddy setup process."""
# ruff: noqa: SLF001

from types import MappingProxyType
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy import async_remove_config_entry_device
from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_NAME,
    CONF_SOLVER,
    CONF_TIMEOUT,
    CONFIG_VER,
    COORDINATOR,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.conftest import _make_hub_entry, _make_station_subentry
from tests.const import COORDINATOR_DATA, STATION_SUBENTRY_DATA

pytestmark = pytest.mark.asyncio


async def test_hub_setup_and_unload(hass, mock_gasbuddy):
    """Test hub entry setup with a station subentry creates sensors and unloads cleanly."""
    entry = _make_hub_entry(hass)
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


async def test_hub_with_no_subentries(hass, mock_gasbuddy):
    """Test hub entry setup with no subentries still sets up without error."""
    entry = _make_hub_entry(hass, subentries=[])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No sensors should be created
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


async def test_legacy_entry_rejected_without_hub(hass, mock_gasbuddy):
    """Test that a legacy (non-hub) entry is automatically migrated into a new hub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data={"name": "Gas Station", "station_id": 999001},
        version=CONFIG_VER,
        unique_id="legacy",
    )
    entry.add_to_hass(hass)

    # Setup the legacy entry. This should return False but trigger hub creation
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify a hub config entry was automatically created
    hub_entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.unique_id == "hub"]
    assert len(hub_entries) == 1
    hub_entry = hub_entries[0]

    # Verify the station was migrated to the hub's subentries
    assert len(hub_entry.subentries) == 1
    sub = next(iter(hub_entry.subentries.values()))
    assert sub.unique_id == "999001"


async def test_remove_config_entry_device(hass, integration):
    """Test async_remove_config_entry_device."""
    assert await async_remove_config_entry_device(hass, integration, None) is True


async def test_options_reload(hass, mock_gasbuddy):
    """Test integration reloads on option changes."""
    entry = _make_hub_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload:
        hass.config_entries.async_update_entry(entry, options={**entry.options, "interval": 1200})
        await hass.async_block_till_done()
        assert mock_reload.called


async def test_service_registration_on_setup(hass, mock_gasbuddy):
    """Test services are registered on setup."""
    entry = _make_hub_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "lookup_gps")


async def test_service_unregistration_on_unload(hass, mock_gasbuddy):
    """Test services are unregistered on unload."""
    entry = _make_hub_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "lookup_gps")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "lookup_gps")


async def test_coordinator_uses_hub_settings(hass, mock_gasbuddy):
    """Test that coordinator reads hub-level settings from the parent config entry."""
    hub_data = {
        CONF_NAME: "GasBuddy Hub",
        CONF_SOLVER: "http://my-solver:8191",
        CONF_TIMEOUT: 30000,
        CONF_BRAND_ADJUSTMENTS: {"Shell": -0.05},
    }
    entry = _make_hub_entry(hass, hub_data=hub_data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    assert len(coordinators) == 1
    coordinator = next(iter(coordinators.values()))

    assert coordinator._get_hub_setting(CONF_SOLVER) == "http://my-solver:8191"
    assert coordinator._get_hub_setting(CONF_TIMEOUT) == 30000


async def test_coordinator_falls_back_to_default(hass, mock_gasbuddy):
    """Test that coordinator falls back to defaults when hub doesn't have a key."""
    hub_data = {CONF_NAME: "GasBuddy Hub"}
    entry = _make_hub_entry(hass, hub_data=hub_data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator = next(iter(coordinators.values()))

    assert coordinator._get_hub_setting(CONF_SOLVER) is None
    assert coordinator._get_hub_setting(CONF_TIMEOUT, DEFAULT_TIMEOUT) == DEFAULT_TIMEOUT


async def test_multiple_station_subentries(hass):
    """Test hub with multiple station subentries creates coordinators for each."""
    sub1 = _make_station_subentry(
        data=MappingProxyType({**STATION_SUBENTRY_DATA, "station_id": 999001}),
        title="Station 1",
        subentry_id="sub1",
        unique_id="999001",
    )
    sub2 = _make_station_subentry(
        data=MappingProxyType({**STATION_SUBENTRY_DATA, "station_id": 999002}),
        title="Station 2",
        subentry_id="sub2",
        unique_id="999002",
    )

    with patch(
        "custom_components.gasbuddy.GasBuddyUpdateCoordinator._async_update_data"
    ) as mock_value:
        mock_value.return_value = COORDINATOR_DATA
        entry = _make_hub_entry(hass, subentries=[sub1, sub2])
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    assert len(coordinators) == 2
    assert "sub1" in coordinators
    assert "sub2" in coordinators


async def test_legacy_entry_auto_hub_creation_failure(hass, mock_gasbuddy):
    """Test that a failure in creating the default hub doesn't crash component setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="gas_station",
        data={"name": "Gas Station", "station_id": 999001},
        version=CONFIG_VER,
        unique_id="legacy",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init",
        side_effect=Exception("Failed to initialize flow"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Hub should not be created
    hub_entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.unique_id == "hub"]
    assert len(hub_entries) == 0


async def test_legacy_entry_migration_race_guard(hass, mock_gasbuddy):
    """Test that concurrent/parallel setup of legacy entries handles the migrating state cleanly."""
    hass.data.setdefault(DOMAIN, {})
    # Simulate a migration already in progress
    hass.data[DOMAIN]["_migrating"] = True

    hub_entry = _make_hub_entry(hass, subentries=[])
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # The migrated flag should have remained True (it wasn't cleaned up by another setup because it was skipped)
    assert hass.data[DOMAIN]["_migrating"] is True


async def test_legacy_migration_full(hass, mock_gasbuddy):
    """Test full migration scenario covering options, solver, timeout, brand adjustments, duplicates, etc."""
    # 1. Create a hub entry
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={},
        version=CONFIG_VER,
    )
    hub_entry.add_to_hass(hass)

    # Another hub entry (to hit entry.unique_id == "hub" continue check)
    hub_entry_dup = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub 2",
        unique_id="hub",
        data={},
        version=CONFIG_VER,
    )
    hub_entry_dup.add_to_hass(hass)

    # 2. Create a legacy entry with station-specific options, solver, timeout, brand_adjustments
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station 1",
        data={
            "name": "Gas Station 1",
            "station_id": 999001,
            "solver": "http://legacy-solver",
            "timeout": 45000,
            "brand_adjustments": {"Shell": 0.05},
        },
        options={"ev_charging": True, "fetch_gas": False, "interval": 3600},
        version=CONFIG_VER,
        unique_id="legacy_1",
    )
    legacy_entry.add_to_hass(hass)

    # Setup legacy_entry when hub already exists (hits L181-182)
    assert not await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    # Verify values migrated to hub
    updated_hub = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.unique_id == "hub")
    assert updated_hub.data.get("solver") == "http://legacy-solver"
    assert updated_hub.data.get("timeout") == 45000
    assert updated_hub.data.get("brand_adjustments") == {"Shell": 0.05}

    # Verify subentry exists with options migrated to data
    assert len(updated_hub.subentries) == 1
    sub = next(iter(updated_hub.subentries.values()))
    assert sub.data.get("ev_charging") is True
    assert sub.data.get("fetch_gas") is False
    assert sub.data.get("interval") == 3600

    # Run setup again on the legacy entry when it's already migrated (hits duplicate unique_id check)
    from custom_components.gasbuddy import _async_migrate_legacy_entries  # noqa: PLC0415, PLC2701

    await _async_migrate_legacy_entries(hass, updated_hub)
