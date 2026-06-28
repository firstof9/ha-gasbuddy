"""Test the GasBuddy config flow."""

from types import MappingProxyType
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_BRAND_ADJUSTMENTS,
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_EXCLUDE_BRANDS,
    CONF_FUEL_KEY,
    CONF_INCLUDE_STATIONS,
    CONF_NAME,
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.asyncio


async def test_hub_config_flow(hass):
    """Test the Virtual Hub config flow."""
    # 1. Initiate flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # 2. Fill form and submit
    with patch(
        "custom_components.gasbuddy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "GasBuddy Hub",
                CONF_SOLVER: "http://flaresolverr:8191",
                CONF_TIMEOUT: 30000,
                CONF_BRAND_ADJUSTMENTS: {"brand_a": -0.05},
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "GasBuddy Hub"
        assert result2["data"][CONF_NAME] == "GasBuddy Hub"
        assert result2["data"][CONF_SOLVER] == "http://flaresolverr:8191"
        assert result2["data"][CONF_TIMEOUT] == 30000
        assert result2["data"][CONF_BRAND_ADJUSTMENTS] == {"brand_a": -0.05}
        assert mock_setup_entry.called


async def test_hub_config_flow_invalid_url(hass):
    """Test the Virtual Hub config flow with an invalid solver URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "GasBuddy Hub",
            CONF_SOLVER: "invalid_url",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"][CONF_SOLVER] == "invalid_url"


async def test_station_subentry_manual_flow(hass):
    """Test adding a station subentry manually."""
    # Setup Hub first
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # 1. Initiate subentry flow
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"), context={"source": "user"}
    )
    assert result["type"] == FlowResultType.MENU
    assert "manual" in result["menu_options"]

    # 2. Select manual step
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    # 3. Submit valid station ID
    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "gas", "latitude": 33.45, "longitude": -112.50},
        ),
        patch("custom_components.gasbuddy.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999001",
                CONF_NAME: "My Station",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My Station"
        assert result["data"][CONF_STATION_ID] == "999001"
        assert result["data"]["latitude"] == 33.45
        assert result["data"][CONF_EV_CHARGING] is False


async def test_station_subentry_search_home_flow(hass):
    """Test searching and adding a station subentry by home coordinates."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"), context={"source": "user"}
    )
    # Go to search sub-menu
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    assert result["type"] == FlowResultType.MENU
    assert "home" in result["menu_options"]

    # Select home search
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "home"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "home"

    # Submit home step to fetch station list
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999001": "Springfield Costco"},
    ):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"

    # Submit home2 selection
    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "gas", "latitude": 33.45, "longitude": -112.50},
        ),
        patch("custom_components.gasbuddy.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999001",
                CONF_NAME: "Springfield Costco",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Springfield Costco"
        assert result["data"][CONF_STATION_ID] == "999001"


async def test_station_subentry_search_postal_flow(hass):
    """Test searching and adding a station subentry by postal code."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    # Select postal search
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )
    assert result["type"] == FlowResultType.MENU or result["type"] == FlowResultType.FORM
    assert result["step_id"] == "postal"

    # Submit valid postal code
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999001": "Springfield Costco"},
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_POSTAL: "85326"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_list"

        # Submit station selection
        with (
            patch(
                "custom_components.gasbuddy.config_flow.validate_station",
                return_value={"type": "gas", "latitude": 33.45, "longitude": -112.50},
            ),
            patch("custom_components.gasbuddy.async_setup_entry", return_value=True),
        ):
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                {
                    CONF_STATION_ID: "999001",
                    CONF_NAME: "Springfield Costco",
                },
            )
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "Springfield Costco"


async def test_station_subentry_cheapest_flow(hass):
    """Test adding a cheapest gas tracker subentry."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "cheapest"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cheapest"

    # Submit cheapest gas config
    with patch(
        "custom_components.gasbuddy.config_flow._get_nearby_brands_and_stations",
        return_value=({"brand_a": "Brand A"}, {"999001": "Costco"}),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Cheapest Gas",
                CONF_FUEL_KEY: "regular_gas",
                CONF_PRICE_TYPE: "best",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "cheapest_filters"

    # Submit filter choices
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_EXCLUDE_BRANDS: ["brand_a"],
            CONF_INCLUDE_STATIONS: ["999001"],
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cheapest Gas"
    assert result["data"][CONF_CHEAPEST] is True
    assert result["data"][CONF_EXCLUDE_BRANDS] == ["brand_a"]
    assert result["data"][CONF_INCLUDE_STATIONS] == ["999001"]


async def test_subentry_reconfigure(hass):
    """Test reconfiguring a station subentry."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # Initialize subentry
    subentry = config_entries.ConfigSubentry(
        subentry_id="test_subentry_id",
        subentry_type="station",
        title="Costco",
        data=MappingProxyType({
            CONF_STATION_ID: "999001",
            CONF_NAME: "Costco",
        }),
        unique_id="999001",
    )
    hass.config_entries.async_add_subentry(hub, subentry)

    # 1. Initiate reconfigure flow
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "999001",
            "subentry_id": "test_subentry_id",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # 2. Submit new station ID
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value={"type": "gas", "latitude": 34.0, "longitude": -118.0},
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999002",
                CONF_NAME: "Costco New",
            },
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        # Subentry updated
        updated_sub = hub.subentries["test_subentry_id"]
        assert updated_sub.data[CONF_STATION_ID] == "999002"
        assert updated_sub.data["latitude"] == 34.0
        assert updated_sub.title == "Costco New"


async def test_hub_options_flow(hass):
    """Test Hub options flow."""
    hub = MockConfigEntry(
        domain=DOMAIN,
        unique_id="hub",
        data={
            CONF_NAME: "GasBuddy Hub",
            CONF_SOLVER: "http://solver-old",
            CONF_TIMEOUT: 60000,
        },
    )
    hub.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "GasBuddy Hub New",
            CONF_SOLVER: "http://solver-new",
            CONF_TIMEOUT: 30000,
            CONF_BRAND_ADJUSTMENTS: {"Shell": -0.10},
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert hub.data[CONF_NAME] == "GasBuddy Hub New"
    assert hub.data[CONF_SOLVER] == "http://solver-new"
    assert hub.data[CONF_TIMEOUT] == 30000
    assert hub.data[CONF_BRAND_ADJUSTMENTS] == {"Shell": -0.10}
