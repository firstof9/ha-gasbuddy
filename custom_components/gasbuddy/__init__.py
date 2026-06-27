"""The ha-gasbuddy component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BRAND_ADJUSTMENTS,
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
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    COORDINATOR,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    SERVICES,
    VERSION,
)
from .coordinator import GasBuddyUpdateCoordinator
from .services import GasBuddyServices

_LOGGER = logging.getLogger(__name__)


async def async_setup(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config: ConfigType
) -> bool:
    """Disallow configuration via YAML."""
    return True


def _migrate_entry_keys(entry: ConfigEntry, hub_data: dict, hub_options: dict) -> None:
    """Migrate settings from a single entry to the hub."""
    for key in (CONF_SOLVER, CONF_TIMEOUT, CONF_BRAND_ADJUSTMENTS):
        val = entry.options.get(key)
        if val is None:
            val = entry.data.get(key)
        if val is None:
            continue

        if key == CONF_BRAND_ADJUSTMENTS:
            if not val:  # skip empty dicts
                continue
            existing_adj = (
                hub_data.get(CONF_BRAND_ADJUSTMENTS)
                or hub_options.get(CONF_BRAND_ADJUSTMENTS)
                or {}
            )
            for brand, adj in val.items():
                if brand in existing_adj and existing_adj[brand] != adj:
                    _LOGGER.warning(
                        "Conflict during brand adjustment migration: '%s' has %s (hub) and %s (entry %s); using %s",
                        brand,
                        existing_adj[brand],
                        adj,
                        entry.entry_id,
                        adj,
                    )
            hub_data[CONF_BRAND_ADJUSTMENTS] = {**existing_adj, **val}
        else:
            is_default = (
                key == CONF_SOLVER and not (hub_data.get(key) or hub_options.get(key))
            ) or (
                key == CONF_TIMEOUT
                and (
                    hub_data.get(key) == DEFAULT_TIMEOUT or hub_options.get(key) == DEFAULT_TIMEOUT
                )
            )
            if hub_data.get(key) is None or is_default:
                hub_data[key] = val


async def _async_setup_hub_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Virtual Hub entry."""
    hub_data = dict(config_entry.data)
    hub_options = dict(config_entry.options)

    if not hub_data.get("migrated"):
        # Sort by entry_id for deterministic migration order.
        # If two stations have conflicting brand adjustments, the one with
        # the lexicographically smaller entry_id wins.
        for entry in sorted(
            hass.config_entries.async_entries(DOMAIN),
            key=lambda e: e.entry_id,
        ):
            if entry.unique_id == "hub":
                continue
            _migrate_entry_keys(entry, hub_data, hub_options)

        try:
            # Commit the hub FIRST — hub_data already has all migrated values
            # from Phase 1 (_migrate_entry_keys). If this fails, stations
            # are untouched and migration will retry on next startup.
            hub_data["migrated"] = True
            hass.config_entries.async_update_entry(config_entry, data=hub_data, options=hub_options)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Hub migration failed; station settings preserved")
            return True

    # Phase 3: Clean up station entries. Checked separately using "stations_cleaned"
    # so we can retry cleanup independently if it fails.
    if hub_data.get("migrated") and not hub_data.get("stations_cleaned"):
        try:
            migrated_count = 0
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.unique_id == "hub":
                    continue

                new_data = dict(entry.data)
                new_options = dict(entry.options)
                cleaned_up = False
                for key in (CONF_SOLVER, CONF_TIMEOUT, CONF_BRAND_ADJUSTMENTS):
                    if key in new_data:
                        new_data.pop(key)
                        cleaned_up = True
                    if key in new_options:
                        new_options.pop(key)
                        cleaned_up = True
                if cleaned_up:
                    hass.config_entries.async_update_entry(
                        entry, data=new_data, options=new_options
                    )
                    migrated_count += 1

            if migrated_count > 0:
                _LOGGER.info("Migrated settings from %d station(s) to Virtual Hub", migrated_count)
            hub_data["stations_cleaned"] = True
            hass.config_entries.async_update_entry(config_entry, data=hub_data)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Station cleanup failed; redundant data remains in station entries")

    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub")},
        name=hub_data.get(CONF_NAME, "GasBuddy Hub"),
        manufacturer="GasBuddy",
        model="Virtual Hub",
    )

    # Link existing station devices to the Virtual Hub device
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == "hub":
            continue
        for dev in device_registry.devices.get_devices_for_config_entry_id(entry.entry_id):
            device_registry.async_update_device(dev.id, via_device_id=hub_device.id)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up is called when Home Assistant is loading our component."""
    if config_entry.unique_id == "hub":
        hass.data.setdefault(DOMAIN, {})
        return await _async_setup_hub_entry(hass, config_entry)

    hass.data.setdefault(DOMAIN, {})
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )

    # Some sanity checks
    updated_config = config_entry.options.copy()
    if CONF_UOM not in config_entry.options:
        updated_config[CONF_UOM] = True
    if CONF_GPS not in config_entry.options:
        updated_config[CONF_GPS] = True
    if CONF_INTERVAL not in config_entry.options:
        updated_config[CONF_INTERVAL] = 3600
    if CONF_EV_CHARGING not in config_entry.options:
        updated_config[CONF_EV_CHARGING] = False
    if CONF_FETCH_GAS not in config_entry.options:
        updated_config[CONF_FETCH_GAS] = True

    if updated_config != config_entry.options:
        hass.config_entries.async_update_entry(config_entry, options=updated_config)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    coordinator = GasBuddyUpdateCoordinator(hass, config_entry)

    # Fetch initial data so we have data when entities subscribe.
    # async_config_entry_first_refresh raises ConfigEntryNotReady itself
    # when the first refresh fails, so HA can schedule a retry instead of
    # leaving setup stalled in a half-loaded state.
    await coordinator.async_config_entry_first_refresh()

    services = GasBuddyServices(hass, config_entry)
    hass.data[DOMAIN][config_entry.entry_id] = {COORDINATOR: coordinator, SERVICES: services}
    services.async_register()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
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

    if config_entry.unique_id == "hub":
        device_registry = dr.async_get(hass)
        for dev in device_registry.devices.get_devices_for_config_entry_id(config_entry.entry_id):
            device_registry.async_remove_device(dev.id)
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
