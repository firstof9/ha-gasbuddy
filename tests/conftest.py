"""Global fixtures for gasbuddy integration."""

import logging
from types import MappingProxyType
from unittest.mock import patch

from aioresponses import aioresponses
import pytest

# Monkeypatch MockConfigEntry to convert non-hub GasBuddy entries to Hub + Subentry
from pytest_homeassistant_custom_component import common
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_EXCLUDE_STATIONS,
    CONF_FETCH_GAS,
    CONF_FUEL_KEY,
    CONF_GPS,
    CONF_INCLUDE_BRANDS,
    CONF_INCLUDE_STATIONS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_PRICE_TYPE,
    CONF_SHOW_DISCOUNTED,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    CONFIG_VER,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentry
from tests.const import COORDINATOR_DATA, COORDINATOR_DATA_CAD, HUB_DATA, STATION_SUBENTRY_DATA

original_init = common.MockConfigEntry.__init__


def patched_init(self, *args, **kwargs):
    """Patch MockConfigEntry.__init__ to convert non-hub GasBuddy entries to Hub + Subentry."""
    domain = kwargs.get("domain") or (args[0] if args else None)
    if domain == "gasbuddy":
        unique_id = kwargs.get("unique_id")
        if unique_id != "hub" and not (unique_id and str(unique_id).startswith("legacy")):
            # Extract legacy data and options
            data = kwargs.get("data", {})
            options = kwargs.get("options", {})

            # Build subentry data
            sub_data = {}
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
                CONF_FUEL_KEY,
                CONF_PRICE_TYPE,
            ):
                if key in data:
                    sub_data[key] = data[key]

            for key in (
                CONF_INTERVAL,
                CONF_UOM,
                CONF_GPS,
                CONF_EV_CHARGING,
                CONF_FETCH_GAS,
                CONF_SHOW_DISCOUNTED,
            ):
                if key in options:
                    sub_data[key] = options[key]
                elif key in data:
                    sub_data[key] = data[key]

            sub_data.setdefault(CONF_INTERVAL, 3600)
            sub_data.setdefault(CONF_UOM, True)
            sub_data.setdefault(CONF_GPS, True)
            sub_data.setdefault(CONF_EV_CHARGING, False)
            sub_data.setdefault(CONF_FETCH_GAS, True)
            sub_data.setdefault(CONF_SHOW_DISCOUNTED, False)
            sub_data.setdefault(CONF_STATION_ID, 999001)

            sub_unique_id = str(data.get(CONF_STATION_ID, 999001))
            sub_data["old_entry_id"] = sub_unique_id

            # Hub data
            hub_data = {
                CONF_NAME: "GasBuddy Hub",
                CONF_SOLVER: data.get(CONF_SOLVER),
                CONF_TIMEOUT: data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                CONF_BRAND_ADJUSTMENTS: options.get(CONF_BRAND_ADJUSTMENTS)
                or data.get(CONF_BRAND_ADJUSTMENTS, {}),
            }

            sub_title = data.get(CONF_NAME, "Gas Station")
            sub_unique_id = str(data.get(CONF_STATION_ID, 999001))
            subentries_data = [
                {
                    "subentry_type": "station",
                    "data": sub_data,
                    "title": sub_title,
                    "unique_id": sub_unique_id,
                    "subentry_id": "test_subentry_id",
                }
            ]

            kwargs["unique_id"] = "hub"
            kwargs["data"] = hub_data
            kwargs["options"] = {}
            kwargs["subentries_data"] = subentries_data
            kwargs["title"] = "GasBuddy Hub"
            kwargs["version"] = CONFIG_VER

    original_init(self, *args, **kwargs)


common.MockConfigEntry.__init__ = patched_init


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration tests."""
    return


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


def _make_station_subentry(
    data: MappingProxyType | dict | None = None,
    title: str = "Gas Station",
    subentry_id: str = "test_subentry_id",
    unique_id: str | None = "999001",
) -> ConfigSubentry:
    """Create a station ConfigSubentry for tests."""
    if data is None:
        data = STATION_SUBENTRY_DATA
    if not isinstance(data, MappingProxyType):
        data = MappingProxyType(data)
    return ConfigSubentry(
        data=data,
        subentry_type="station",
        title=title,
        unique_id=unique_id,
        subentry_id=subentry_id,
    )


def _make_hub_entry(
    hass,
    hub_data: dict | None = None,
    subentries: list[ConfigSubentry] | None = None,
) -> MockConfigEntry:
    """Create a hub MockConfigEntry with station subentries."""
    if hub_data is None:
        hub_data = dict(HUB_DATA)
    if subentries is None:
        subentries = [_make_station_subentry()]

    subentries_list = [
        {
            "subentry_type": sub.subentry_type,
            "data": dict(sub.data),
            "title": sub.title,
            "unique_id": sub.unique_id,
            "subentry_id": sub.subentry_id,
        }
        for sub in subentries
    ]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=hub_data.get("name", "GasBuddy Hub"),
        data=hub_data,
        unique_id="hub",
        version=CONFIG_VER,
        subentries_data=subentries_list,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_gasbuddy():
    """Mock charger data."""
    with patch(
        "custom_components.gasbuddy.GasBuddyUpdateCoordinator._async_update_data"
    ) as mock_value:
        mock_value.return_value = COORDINATOR_DATA
        yield


@pytest.fixture
def mock_gasbuddy_cad():
    """Mock charger data."""
    with patch(
        "custom_components.gasbuddy.GasBuddyUpdateCoordinator._async_update_data"
    ) as mock_value:
        mock_value.return_value = COORDINATOR_DATA_CAD
        yield


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m


@pytest.fixture(name="hub_entry")
async def hub_entry_fixture(hass, mock_gasbuddy):
    """Set up a GasBuddy Hub integration with a default station subentry."""
    entry = _make_hub_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(name="integration")
async def integration_fixture(hass, mock_gasbuddy):
    """Set up the GasBuddy Hub integration (alias for hub_entry)."""
    entry = _make_hub_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(autouse=True)
def set_caplog_debug_level(caplog):
    """Force DEBUG log capture for tests that use caplog."""
    caplog.set_level(logging.DEBUG)
