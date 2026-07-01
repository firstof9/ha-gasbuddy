"""Test gasbuddy setup process."""
# ruff: noqa: SLF001

import contextlib
from types import MappingProxyType
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy import async_remove_config_entry_device
from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_NAME,
    CONF_SOLVER,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    COORDINATOR,
    DEFAULT_TIMEOUT,
    DOMAIN,
    CoordinatorsDict,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers import device_registry as dr, entity_registry as er
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

    # Falsy-value regression: CONF_TIMEOUT=0 must return 0, not fall back to default
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_TIMEOUT: 0})
    await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator = next(iter(coordinators.values()))
    assert coordinator._get_hub_setting(CONF_TIMEOUT) == 0

    assert coordinator._get_hub_setting("nonexistent_key", "fallback") == "fallback"


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


async def test_legacy_migration_failure_preserves_station_settings(hass, mock_gasbuddy):
    """Test that station settings are preserved when the hub async_update_entry call fails.

    Addresses CodeRabbit finding: the migration-failure test must assert that station
    data (solver/timeout/brand_adjustments) is NOT stripped when updating the hub raises.
    """
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={},
        version=CONFIG_VER,
    )
    hub_entry.add_to_hass(hass)

    # Station entry with global settings that should be migrated to the hub
    failure_station = MockConfigEntry(
        domain=DOMAIN,
        title="Failure Station",
        data={
            "name": "Failure Station",
            "station_id": 777001,
            CONF_SOLVER: "http://solver",
            CONF_BRAND_ADJUSTMENTS: {"BrandB": -0.07},
        },
        options={CONF_TIMEOUT: 15000},
        version=CONFIG_VER,
        unique_id="legacy_failure_1",
    )
    failure_station.add_to_hass(hass)

    from custom_components.gasbuddy import _async_migrate_legacy_entries  # noqa: PLC0415, PLC2701

    # Patch async_update_entry to fail — this simulates a transient HA error during hub data commit
    original_update = hass.config_entries.async_update_entry
    call_count = 0
    hub_update_called = False

    def fail_update_entry(entry, **kwargs):
        nonlocal call_count, hub_update_called
        call_count += 1
        # Fail only the hub data update (not subentry metadata updates)
        if entry.entry_id == hub_entry.entry_id and "data" in kwargs:
            hub_update_called = True
            raise RuntimeError("Simulated hub update failure")
        return original_update(entry, **kwargs)

    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=fail_update_entry),
        contextlib.suppress(RuntimeError),
    ):
        await _async_migrate_legacy_entries(hass, hub_entry)
    await hass.async_block_till_done()

    assert hub_update_called is True

    # Station entry should still have its original settings (async_remove never ran)
    preserved_station = hass.config_entries.async_get_entry(failure_station.entry_id)
    assert preserved_station is not None, "Station entry must not have been removed"
    assert preserved_station.data[CONF_SOLVER] == "http://solver"
    assert preserved_station.data[CONF_BRAND_ADJUSTMENTS] == {"BrandB": -0.07}
    assert preserved_station.options[CONF_TIMEOUT] == 15000


async def test_subentry_removal_cleanup(hass, mock_gasbuddy):
    """Test that deleting a station subentry cleans up its device and entity registry entries."""
    entry = _make_hub_entry(hass)
    subentry = next(iter(entry.subentries.values()))

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify device and entity registries have entries for the subentry
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device = dev_reg.async_get_device(identifiers={(DOMAIN, subentry.subentry_id)})
    assert device is not None
    assert subentry.subentry_id in device.config_entries_subentries.get(entry.entry_id, set())

    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    sub_entities = [e for e in entities if e.config_subentry_id == subentry.subentry_id]
    assert len(sub_entities) > 0

    # Simulate subentry deletion: remove subentry from config entry
    hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    await hass.async_block_till_done()

    # Reload integration to trigger async_setup_entry and cleanup
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Verify device and entities are purged
    assert dev_reg.async_get_device(identifiers={(DOMAIN, subentry.subentry_id)}) is None
    entities_post = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    sub_entities_post = [e for e in entities_post if e.config_subentry_id == subentry.subentry_id]
    assert len(sub_entities_post) == 0


async def test_migrate_entry_from_v1(hass):
    """Test async_migrate_entry migrates from version 1 (missing UOM + GPS + solver + timeout + lists + brand_adj)."""
    from custom_components.gasbuddy import async_migrate_entry  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={"name": "Gas Station", "station_id": 999001},
        unique_id="hub",
        version=1,
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.version == CONFIG_VER
    assert updated.data.get(CONF_UOM) is True
    assert updated.data.get(CONF_GPS) is True
    assert CONF_SOLVER in updated.data
    assert updated.data.get(CONF_TIMEOUT) == 60000
    assert updated.data.get(CONF_EXCLUDE_BRANDS) == []
    assert updated.data.get(CONF_INCLUDE_BRANDS) == []
    assert updated.data.get(CONF_EXCLUDE_STATIONS) == []
    assert updated.data.get(CONF_INCLUDE_STATIONS) == []
    assert updated.data.get(CONF_BRAND_ADJUSTMENTS) == {}


async def test_migrate_entry_from_v5(hass):
    """Test async_migrate_entry migrates from version 5 (missing solver + timeout + lists + brand_adj)."""
    from custom_components.gasbuddy import async_migrate_entry  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={"name": "Gas Station", "station_id": 999001, CONF_UOM: True, CONF_GPS: True},
        unique_id="hub",
        version=5,
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.version == CONFIG_VER
    assert CONF_SOLVER in updated.data
    assert updated.data.get(CONF_TIMEOUT) == 60000
    assert updated.data.get(CONF_EXCLUDE_BRANDS) == []
    assert updated.data.get(CONF_BRAND_ADJUSTMENTS) == {}


async def test_migrate_entry_from_v8(hass):
    """Test async_migrate_entry migrates from version 8 (only missing brand_adjustments)."""
    from custom_components.gasbuddy import async_migrate_entry  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={
            "name": "Gas Station",
            "station_id": 999001,
            CONF_UOM: True,
            CONF_GPS: True,
            CONF_SOLVER: None,
            CONF_TIMEOUT: 60000,
            CONF_EXCLUDE_BRANDS: [],
            CONF_INCLUDE_BRANDS: [],
            CONF_EXCLUDE_STATIONS: [],
            CONF_INCLUDE_STATIONS: [],
        },
        unique_id="hub",
        version=8,
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.version == CONFIG_VER
    assert updated.data.get(CONF_BRAND_ADJUSTMENTS) == {}


async def test_migrate_entry_already_current(hass):
    """Test async_migrate_entry when entry is already at current version — no update needed."""
    from custom_components.gasbuddy import async_migrate_entry  # noqa: PLC0415

    full_data = {
        "name": "Gas Station",
        "station_id": 999001,
        CONF_UOM: True,
        CONF_GPS: True,
        CONF_SOLVER: None,
        CONF_TIMEOUT: 60000,
        CONF_EXCLUDE_BRANDS: [],
        CONF_INCLUDE_BRANDS: [],
        CONF_EXCLUDE_STATIONS: [],
        CONF_INCLUDE_STATIONS: [],
        CONF_BRAND_ADJUSTMENTS: {},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=full_data,
        unique_id="hub",
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.version == CONFIG_VER


async def test_non_station_subentry_skipped(hass, mock_gasbuddy):
    """Test that non-station subentries are skipped and no coordinator is created for them."""
    # Create a hub with a subentry that has subentry_type != "station"
    non_station_sub = ConfigSubentry(
        data=MappingProxyType({"name": "My Cheapest Tracker"}),
        subentry_type="cheapest",
        title="Cheapest Gas",
        unique_id="cheapest_001",
        subentry_id="cheapest_sub_id",
    )
    station_sub = _make_station_subentry()
    entry = _make_hub_entry(hass, subentries=[station_sub, non_station_sub])

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Only the station subentry should have a coordinator
    coordinators = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    assert len(coordinators) == 1
    assert station_sub.subentry_id in coordinators
    assert "cheapest_sub_id" not in coordinators


async def test_legacy_entry_unload(hass):
    """Test that unloading a legacy (non-hub) entry returns True immediately."""
    from custom_components.gasbuddy import async_unload_entry  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={"name": "Gas Station", "station_id": 999001},
        unique_id="legacy_unload_999",
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)

    # Call async_unload_entry directly for a non-hub entry — it should return True
    result = await async_unload_entry(hass, entry)
    assert result is True


async def test_entity_registry_cleanup_on_removed_subentry(hass, mock_gasbuddy):
    """Test that entity registry entries for removed subentries are cleaned up."""
    sub1 = _make_station_subentry(subentry_id="sub_keep", unique_id="999001")
    sub2 = _make_station_subentry(
        data=MappingProxyType({**STATION_SUBENTRY_DATA, "station_id": 999002}),
        title="Station 2",
        subentry_id="sub_remove",
        unique_id="999002",
    )
    entry = _make_hub_entry(hass, subentries=[sub1, sub2])

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    sub2_entities = [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.config_subentry_id == "sub_remove"
    ]
    assert len(sub2_entities) > 0

    # Remove sub2
    hass.config_entries.async_remove_subentry(entry, "sub_remove")
    await hass.async_block_till_done()

    # Reload to trigger async_setup_entry cleanup
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # sub_remove entities should be gone
    remaining = [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.config_subentry_id == "sub_remove"
    ]
    assert len(remaining) == 0

    # sub_keep entities should still exist
    kept = [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.config_subentry_id == "sub_keep"
    ]
    assert len(kept) > 0


async def test_migrate_legacy_entries_duplicate_unique_id(hass, mock_gasbuddy):
    """Test that _async_migrate_legacy_entries skips legacy entries whose unique_id already exists in the hub."""
    from custom_components.gasbuddy import _async_migrate_legacy_entries  # noqa: PLC0415, PLC2701

    # Create a hub entry that already has a subentry with unique_id "999001"
    existing_sub = _make_station_subentry(subentry_id="existing_sub", unique_id="999001")
    hub_entry = _make_hub_entry(hass, subentries=[existing_sub])

    # Create a legacy station entry with station_id 999001 (same unique_id as existing sub)
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data={"name": "Gas Station", "station_id": 999001},
        version=CONFIG_VER,
        unique_id="legacy_dup",
    )
    legacy_entry.add_to_hass(hass)

    # Run migration — the legacy entry's unique_id "999001" is already present so it should be skipped (L143)
    await _async_migrate_legacy_entries(hass, hub_entry)
    await hass.async_block_till_done()

    # Hub should still have only the original subentry (no new one added)
    updated_hub = hass.config_entries.async_get_entry(hub_entry.entry_id)
    assert len(updated_hub.subentries) == 1
    assert next(iter(updated_hub.subentries.values())).subentry_id == "existing_sub"


async def test_entity_only_orphan_cleanup(hass, mock_gasbuddy):
    """Test that orphaned entity registry entries (no device) with stale subentry ids are cleaned up.

    Simulates the case where an entity ends up in the registry with a config_subentry_id
    that no longer exists in the parent config entry (lines 254-259 in __init__.py).
    """
    import attr  # noqa: PLC0415

    entry = _make_hub_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    subentry = next(iter(entry.subentries.values()))

    # Get an existing entity registered under the subentry
    existing_entities = [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.config_subentry_id == subentry.subentry_id
    ]
    assert existing_entities, "Expected at least one entity under the subentry"

    # Clone the entity with a completely stale subentry id (bypassing HA validation)
    stale_subentry_id = "orphan_stale_subentry_id"
    stale_entity = attr.evolve(
        existing_entities[0],
        entity_id="sensor.gasbuddy_orphan_stale",
        unique_id="gasbuddy_orphan_stale_unique",
        config_subentry_id=stale_subentry_id,
        device_id=None,  # no device so device cascade won't clean it up
        id=None,  # generate a fresh registry id to avoid collision
    )

    # Inject the stale entity into the registry's internal data, bypassing subentry validation
    ent_reg.entities._index_entry(stale_entity.entity_id, stale_entity)
    ent_reg.entities.data[stale_entity.entity_id] = stale_entity

    # Confirm the stale entity is visible in the registry
    assert ent_reg.async_get(stale_entity.entity_id) is not None

    # Remove the real subentry so the hub entry no longer has subentry_id in its subentries
    hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    await hass.async_block_till_done()

    # Reload to trigger async_setup_entry cleanup (lines 249-259)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # The stale entity should have been removed by the cleanup
    assert ent_reg.async_get(stale_entity.entity_id) is None


async def test_setup_ignores_hub_subentry(hass, mock_gasbuddy, caplog):
    """Test that a subentry with unique_id or subentry_id 'hub' is ignored during setup."""
    sub_real = _make_station_subentry(unique_id="999001", subentry_id="test_subentry_id")
    sub_hub = _make_station_subentry(unique_id="hub", subentry_id="hub")

    entry = _make_hub_entry(hass, subentries=[sub_real, sub_hub])
    entry.add_to_hass(hass)

    import logging  # noqa: PLC0415

    with caplog.at_level(logging.WARNING):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "Ignoring invalid station subentry: hub" in caplog.text


async def test_coordinators_dict_empty():
    """Test CoordinatorsDict behavior when empty (covers lines 406 and 422 in const.py)."""
    empty_dict = CoordinatorsDict()
    # Test data property getter when empty (covers L406)
    assert empty_dict.data == {}

    # Test __getattr__ delegation when empty raises AttributeError (covers L422)
    with pytest.raises(
        AttributeError, match="'CoordinatorsDict' object has no attribute 'some_attribute'"
    ):
        _ = empty_dict.some_attribute


async def test_legacy_migration_entry_exception_skipped(hass, mock_gasbuddy, caplog):
    """Test migration loop skips a bad legacy entry and continues with remaining stations.

    Covers __init__.py lines 154-155: the except-block in _async_migrate_legacy_entries
    that logs a warning and moves on when a single station fails to build its subentry.
    """
    from unittest.mock import patch  # noqa: PLC0415

    from custom_components.gasbuddy import _async_migrate_legacy_entries  # noqa: PLC0415, PLC2701
    from homeassistant.config_entries import ConfigSubentry  # noqa: PLC0415

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GasBuddy Hub",
        unique_id="hub",
        data={},
        options={},
        version=CONFIG_VER,
    )
    hub_entry.add_to_hass(hass)

    # First legacy entry — will fail during subentry construction.
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bad Station",
        data={"name": "Bad Station", "station_id": 111001},
        version=CONFIG_VER,
        unique_id="legacy_bad",
    )
    bad_entry.add_to_hass(hass)

    # Second legacy entry — should migrate successfully despite bad_entry failing.
    good_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Good Station",
        data={"name": "Good Station", "station_id": 111002},
        version=CONFIG_VER,
        unique_id="legacy_good",
    )
    good_entry.add_to_hass(hass)

    call_count = 0
    original_subentry_init = ConfigSubentry.__init__

    def _patched_subentry_init(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Raise on the first ConfigSubentry construction (bad_entry), succeed on the second.
        if call_count == 1:
            raise ValueError("Simulated corrupt subentry data")
        return original_subentry_init(self, *args, **kwargs)

    import logging  # noqa: PLC0415

    with (
        patch.object(ConfigSubentry, "__init__", _patched_subentry_init),
        caplog.at_level(logging.WARNING),
    ):
        await _async_migrate_legacy_entries(hass, hub_entry)
    await hass.async_block_till_done()

    # The warning must mention the failing entry.
    assert "Migration failed for legacy entry" in caplog.text

    # The good entry must have been migrated as a subentry.
    updated_hub = hass.config_entries.async_get_entry(hub_entry.entry_id)
    sub_unique_ids = {sub.unique_id for sub in updated_hub.subentries.values()}
    assert "111002" in sub_unique_ids
