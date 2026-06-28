"""The ha-gasbuddy component."""

from __future__ import annotations

import asyncio
import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    COORDINATOR,
    DEFAULT_TIMEOUT as DEFAULT_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    SERVICES,
    VERSION,
    CoordinatorsDict,
)
from .coordinator import GasBuddyUpdateCoordinator
from .services import GasBuddyServices

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config: ConfigType
) -> bool:
    """Disallow configuration via YAML."""
    return True


def _build_subentry_data_from_entry(entry: ConfigEntry) -> dict:
    """Build subentry data dict from a legacy standalone station config entry."""
    data: dict = {}
    # Station-specific keys from entry.data
    for key in (
        CONF_STATION_ID,
        CONF_NAME,
        CONF_CHEAPEST,
        "latitude",
        "longitude",
        CONF_EXCLUDE_BRANDS,
        CONF_INCLUDE_BRANDS,
        CONF_EXCLUDE_STATIONS,
        CONF_INCLUDE_STATIONS,
    ):
        if key in entry.data:
            data[key] = entry.data[key]

    # Station-specific keys from entry.options (these become subentry data)
    for key in (
        CONF_INTERVAL,
        CONF_UOM,
        CONF_GPS,
        CONF_EV_CHARGING,
        CONF_FETCH_GAS,
    ):
        if key in entry.options:
            data[key] = entry.options[key]

    # Preserve original entry_id for unique_id continuity
    data["old_entry_id"] = entry.entry_id

    return data


async def _async_migrate_legacy_entries(hass: HomeAssistant, hub_entry: ConfigEntry) -> None:
    """Migrate standalone station config entries into subentries of the hub."""
    entries_to_remove = []
    updated_hub_data = {}

    solver_url = hub_entry.data.get(CONF_SOLVER)
    timeout = hub_entry.data.get(CONF_TIMEOUT)
    brand_adjustments = dict(hub_entry.data.get(CONF_BRAND_ADJUSTMENTS, {}))

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == hub_entry.entry_id:
            continue
        if entry.unique_id == "hub":
            # Another hub entry — shouldn't happen, but skip
            continue

        # Try to extract global settings from legacy entry if not set on the Hub
        if not solver_url:
            legacy_solver = entry.data.get(CONF_SOLVER) or entry.options.get(CONF_SOLVER)
            if legacy_solver:
                solver_url = legacy_solver
                updated_hub_data[CONF_SOLVER] = solver_url

        if not timeout:
            legacy_timeout = entry.data.get(CONF_TIMEOUT) or entry.options.get(CONF_TIMEOUT)
            if legacy_timeout:
                timeout = legacy_timeout
                updated_hub_data[CONF_TIMEOUT] = timeout

        legacy_brand_adj = entry.data.get(CONF_BRAND_ADJUSTMENTS) or entry.options.get(
            CONF_BRAND_ADJUSTMENTS
        )
        if legacy_brand_adj:
            brand_adjustments.update(legacy_brand_adj)
            updated_hub_data[CONF_BRAND_ADJUSTMENTS] = brand_adjustments

        subentry_data = _build_subentry_data_from_entry(entry)
        station_name = entry.data.get(CONF_NAME, entry.title or "Gas Station")

        subentry = ConfigSubentry(
            data=MappingProxyType(subentry_data),
            subentry_type="station",
            title=station_name,
            unique_id=str(entry.data.get(CONF_STATION_ID, entry.unique_id)),
        )

        if subentry.unique_id in {sub.unique_id for sub in hub_entry.subentries.values()}:
            continue

        hass.config_entries.async_add_subentry(hub_entry, subentry)
        _LOGGER.info(
            "Migrated station '%s' (entry %s) to subentry %s",
            station_name,
            entry.entry_id,
            subentry.subentry_id,
        )
        entries_to_remove.append(entry.entry_id)

    if updated_hub_data:
        hass.config_entries.async_update_entry(
            hub_entry,
            data={**hub_entry.data, **updated_hub_data},
        )

    for entry_id in entries_to_remove:
        await hass.config_entries.async_remove(entry_id)

    if entries_to_remove:
        _LOGGER.info(
            "Completed migration of %d station(s) to hub subentries",
            len(entries_to_remove),
        )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up is called when Home Assistant is loading our component."""
    hass.data.setdefault(DOMAIN, {})

    # Legacy standalone station entries: if this entry is NOT a hub,
    # check if a hub already exists and migrate this entry, or set it up
    # the old way until a hub is created.
    if config_entry.unique_id != "hub":
        # A hub exists — this legacy entry should have been migrated.
        # Trigger migration now and abort setup for this entry.
        hub_entry = next(
            (e for e in hass.config_entries.async_entries(DOMAIN) if e.unique_id == "hub"),
            None,
        )
        if hub_entry is not None:
            await _async_migrate_legacy_entries(hass, hub_entry)
            return False
        # No hub exists yet — create a default Virtual Hub config entry automatically!
        _LOGGER.info("No GasBuddy Hub exists. Automatically creating a default GasBuddy Hub.")

        async def _async_create_hub() -> None:
            await asyncio.sleep(0.1)
            try:
                await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "user"},
                    data={
                        CONF_NAME: "GasBuddy Hub",
                        CONF_SOLVER: "",
                        CONF_TIMEOUT: 60000,
                        CONF_BRAND_ADJUSTMENTS: {},
                    },
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to automatically create GasBuddy Hub. "
                    "Please create it manually via the Integrations UI."
                )

        hass.async_create_task(_async_create_hub())
        return False

    # --- Hub entry setup ---
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )

    # Migrate any remaining legacy station entries.
    # Guard against concurrent migration calls (e.g., multiple legacy entries
    # loading in parallel during HA restart).
    domain_data = hass.data[DOMAIN]
    if not domain_data.get("_migrating"):
        legacy_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != config_entry.entry_id and e.unique_id != "hub"
        ]
        if legacy_entries:
            domain_data["_migrating"] = True
            try:
                await _async_migrate_legacy_entries(hass, config_entry)
            finally:
                domain_data.pop("_migrating", None)

    # Set up coordinators for each station subentry
    device_registry = dr.async_get(hass)
    coordinators: dict[str, GasBuddyUpdateCoordinator] = {}
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "station":
            continue

        coordinator = GasBuddyUpdateCoordinator(hass, config_entry, subentry)
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry.subentry_id] = coordinator

        # Ensure station device exists
        old_entry_id = subentry.data.get("old_entry_id")
        station_id = old_entry_id if old_entry_id is not None else subentry.subentry_id
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            config_subentry_id=subentry.subentry_id,
            identifiers={(DOMAIN, station_id)},
            name=subentry.title,
            manufacturer="GasBuddy",
        )

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: CoordinatorsDict(coordinators),
    }

    # Register services
    services = GasBuddyServices(hass, config_entry)
    hass.data[DOMAIN][config_entry.entry_id][SERVICES] = services
    services.async_register()

    # Forward sensor platform setup
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER
    updated_config = config_entry.data.copy()

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Migrate format
    if version == 1:
        # Add default unit of measure setting if missing
        if CONF_UOM not in updated_config:
            updated_config[CONF_UOM] = True

    if version < 5:
        if CONF_GPS not in updated_config:
            updated_config[CONF_GPS] = True

    if version < 6:
        if CONF_SOLVER not in updated_config:
            updated_config[CONF_SOLVER] = None

    if version < 7:
        if CONF_TIMEOUT not in updated_config:
            updated_config[CONF_TIMEOUT] = 60000

    if version < 8:
        for key in (
            CONF_EXCLUDE_BRANDS,
            CONF_INCLUDE_BRANDS,
            CONF_EXCLUDE_STATIONS,
            CONF_INCLUDE_STATIONS,
        ):
            if key not in updated_config:
                updated_config[key] = []

    if version < 9:
        if CONF_BRAND_ADJUSTMENTS not in updated_config:
            updated_config[CONF_BRAND_ADJUSTMENTS] = {}

    # Persist the bumped version even when no data keys changed; otherwise
    # the entry stays on the old version and HA re-runs migration every start.
    if updated_config != config_entry.data or config_entry.version != new_version:
        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=new_version
        )

    _LOGGER.debug("Migration to version %s complete", CONFIG_VER)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload entities from the %s integration", DOMAIN)

    if config_entry.unique_id != "hub":
        # Legacy entry — nothing to unload
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload_ok:
        _LOGGER.debug("Successfully removed entities from the %s integration", DOMAIN)
        entry_data = hass.data.get(DOMAIN, {}).pop(config_entry.entry_id, None)
        if entry_data and (services := entry_data.get(SERVICES)):
            services.async_unregister()

    return unload_ok


async def async_remove_config_entry_device(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    _LOGGER.debug("Removing device from the %s integration", DOMAIN)

    return True
