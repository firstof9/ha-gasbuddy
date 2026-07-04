"""Test the GasBuddy config flow."""

from types import MappingProxyType
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.config_flow import CloudflareBlocked, InvalidStation
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
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SHOW_DISCOUNTED,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
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


async def test_subentry_reconfigure_options(hass):
    """Test reconfiguring station subentry options (both when ID changes and when it doesn't)."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # Initialize subentry with custom options
    subentry = config_entries.ConfigSubentry(
        subentry_id="test_subentry_id_opts",
        subentry_type="station",
        title="Costco Options",
        data=MappingProxyType({
            CONF_STATION_ID: "999001",
            CONF_NAME: "Costco Options",
            CONF_INTERVAL: 1800,
            CONF_UOM: False,
            CONF_GPS: False,
            CONF_EV_CHARGING: True,
            CONF_FETCH_GAS: False,
            CONF_SHOW_DISCOUNTED: True,
        }),
        unique_id="999001",
    )
    hass.config_entries.async_add_subentry(hub, subentry)

    # 1. Initiate reconfigure flow (without ID change, toggling options)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "999001",
            "subentry_id": "test_subentry_id_opts",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Submit updated options (keeping ID same, but toggling other settings)
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value={"type": "gas", "latitude": 33.45, "longitude": -112.50},
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999001",
                CONF_NAME: "Costco Options Updated",
                CONF_INTERVAL: 7200,
                CONF_UOM: True,
                CONF_GPS: True,
                CONF_EV_CHARGING: False,
                CONF_FETCH_GAS: True,
                CONF_SHOW_DISCOUNTED: False,
            },
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        # Subentry updated and options preserved/updated rather than overwritten by validator
        updated_sub = hub.subentries["test_subentry_id_opts"]
        assert updated_sub.data[CONF_STATION_ID] == "999001"
        assert updated_sub.data[CONF_INTERVAL] == 7200
        assert updated_sub.data[CONF_UOM] is True
        assert updated_sub.data[CONF_GPS] is True
        assert updated_sub.data[CONF_EV_CHARGING] is False
        assert updated_sub.data[CONF_FETCH_GAS] is True
        assert updated_sub.data[CONF_SHOW_DISCOUNTED] is False
        assert updated_sub.title == "Costco Options Updated"

    # 2. Reconfigure station ID to a different one (should overwrite EV/gas settings)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "999001",
            "subentry_id": "test_subentry_id_opts",
        },
    )
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value={"type": "ev", "latitude": 33.5, "longitude": -112.6},
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999002",
                CONF_NAME: "EV Station",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_GPS: True,
                CONF_EV_CHARGING: False,  # overridden because ID changed
                CONF_FETCH_GAS: True,  # overridden because ID changed
                CONF_SHOW_DISCOUNTED: False,
            },
        )
        assert result["type"] == FlowResultType.ABORT
        updated_sub = hub.subentries["test_subentry_id_opts"]
        assert updated_sub.data[CONF_STATION_ID] == "999002"
        # Auto-detected ev station type overwrites values submitted:
        assert updated_sub.data[CONF_EV_CHARGING] is True
        assert updated_sub.data[CONF_FETCH_GAS] is False


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


async def test_subentry_reconfigure_edge_cases(hass):
    """Test various edge cases when reconfiguring a station subentry."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # 1. Cheapest station reconfiguration
    subentry_cheapest = config_entries.ConfigSubentry(
        subentry_id="sub_cheapest",
        subentry_type="station",
        title="Cheapest",
        data=MappingProxyType({
            CONF_CHEAPEST: True,
            CONF_NAME: "Cheapest",
        }),
        unique_id="cheapest",
    )
    hass.config_entries.async_add_subentry(hub, subentry_cheapest)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "cheapest",
            "subentry_id": "sub_cheapest",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure_cheapest"

    # 2. Regular station reconfiguration error paths
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

    # Check invalid format: _STATION_ID_RE mismatch (non-numeric/alphabetic)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "999001",
            "subentry_id": "test_subentry_id",
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: "abc-def",
            CONF_NAME: "Costco New",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATION_ID] == "station_id"

    # Check CloudflareBlocked exception
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999002",
                CONF_NAME: "Costco New",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_STATION_ID] == "cloudflare"

    # Check InvalidStation exception
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=InvalidStation,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: "999002",
                CONF_NAME: "Costco New",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_STATION_ID] == "station_id"

    # Check non-dict validation return (returns True)
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
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
        # Subentry updated with defaults for ev_charging/fetch_gas
        updated_sub = hub.subentries["test_subentry_id"]
        assert updated_sub.data[CONF_EV_CHARGING] is False
        assert updated_sub.data[CONF_FETCH_GAS] is True


async def test_station_subentry_manual_invalid_format(hass):
    """Test manual station subentry flow with invalid format."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
    )
    assert result["step_id"] == "manual"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: "abc-def",
            CONF_NAME: "Manual",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATION_ID] == "station_id"


# ── Additional Coverage Tests for config_flow.py ───────────────────────────


from py_gasbuddy.exceptions import (  # noqa: E402
    APIError,
    CSRFTokenMissing,
    LibraryError,
    MissingSearchData,
)

from custom_components.gasbuddy.config_flow import (  # noqa: E402
    SearchFailed,
    _get_nearby_brands_and_stations,  # noqa: PLC2701
    _get_schema_options,  # noqa: PLC2701
    _get_station_list,  # noqa: PLC2701
    _lon_delta,  # noqa: PLC2701
    validate_station,
)


async def test_lon_delta_antimeridian():
    """Test _lon_delta handles the antimeridian boundary."""
    assert _lon_delta(179.9, -179.9) == pytest.approx(0.2)
    assert _lon_delta(10.0, 20.0) == pytest.approx(10.0)


async def test_validate_station_cloudflare_blocked(hass):
    """Test validate_station raising CloudflareBlocked on CSRFTokenMissing and LibraryError with cf_last=False."""
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup", side_effect=CSRFTokenMissing),
        pytest.raises(CloudflareBlocked),
    ):
        await validate_station(hass, 999001)

    with (
        patch("py_gasbuddy.GasBuddy.price_lookup", side_effect=LibraryError),
        patch(
            "custom_components.gasbuddy.config_flow._csrf_blocked_via_state",
            return_value=True,
        ),
        pytest.raises(CloudflareBlocked),
    ):
        await validate_station(hass, 999001)


async def test_validate_station_ev_failure_invalid_station(hass):
    """Test validate_station error handling on EV check exceptions and returning False."""
    # Price lookup fails, EV lookup raises Exception
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup", side_effect=APIError("Price lookup error")),
        patch(
            "py_gasbuddy.GasBuddy.ev_stations_nearby",
            side_effect=ValueError("EV lookup exception"),
        ),
        pytest.raises(InvalidStation),
    ):
        await validate_station(hass, 999001)

    # Price lookup succeeds but has "errors" in response, EV lookup finds nothing -> returns False
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup", return_value={"errors": "Some error"}),
        patch("py_gasbuddy.GasBuddy.ev_stations_nearby", return_value={"stations": []}),
    ):
        res = await validate_station(hass, 999001)
        assert res is False


async def test_get_station_list_edge_cases(hass):
    """Test _get_station_list edge cases."""
    # Falsy postal, uses home coords, solver configured
    hass.config.latitude = 41.8781
    hass.config.longitude = -87.6298
    with patch("py_gasbuddy.GasBuddy.location_search", return_value={"results": []}) as mock_search:
        res = await _get_station_list(hass, {CONF_POSTAL: "", CONF_SOLVER: "http://solver"})
        mock_search.assert_called_once_with(lat=41.8781, lon=-87.6298, zipcode=None)
        assert res == {"not_found": "No stations in search area."}

    # MissingSearchData exception raises SearchFailed
    with (
        patch("py_gasbuddy.GasBuddy.location_search", side_effect=MissingSearchData),
        pytest.raises(SearchFailed),
    ):
        await _get_station_list(hass, {CONF_POSTAL: "12345"})

    # Station ID is None in search results
    with patch(
        "py_gasbuddy.GasBuddy.location_search",
        return_value={"results": [{"station_id": None, "name": "No ID"}]},
    ):
        res = await _get_station_list(hass, {CONF_POSTAL: "12345"})
        assert res == {"not_found": "No stations in search area."}

    # Resolve postal code coordinates failure in EV flow
    with (
        patch("py_gasbuddy.GasBuddy.location_search", return_value={"results": []}),
        patch(
            "py_gasbuddy.GasBuddy.price_lookup_service",
            side_effect=RuntimeError("Postal lookup failed"),
        ),
    ):
        res = await _get_station_list(hass, {CONF_POSTAL: "12345"})
        assert res == {"not_found": "No stations in search area."}

    # EV stations lookup exception
    with (
        patch("py_gasbuddy.GasBuddy.location_search", return_value={"results": []}),
        patch(
            "py_gasbuddy.GasBuddy.price_lookup_service",
            return_value={"results": [{"latitude": 40.0, "longitude": -80.0}]},
        ),
        patch(
            "py_gasbuddy.GasBuddy.ev_stations_nearby",
            side_effect=ValueError("EV error"),
        ),
    ):
        res = await _get_station_list(hass, {CONF_POSTAL: "12345"})
        assert res == {"not_found": "No stations in search area."}

    # Cache cleanup when flows exceed 50
    hass.data.setdefault(DOMAIN, {})
    coord_cache = hass.data[DOMAIN].setdefault("station_coordinates_by_flow", {})
    coord_cache.clear()
    for i in range(50):
        coord_cache[f"flow_{i}"] = {}
    with (
        patch("py_gasbuddy.GasBuddy.location_search", return_value={"results": []}),
        patch(
            "py_gasbuddy.GasBuddy.price_lookup_service",
            return_value={"results": [{"latitude": 40.0, "longitude": -80.0}]},
        ),
        patch(
            "py_gasbuddy.GasBuddy.ev_stations_nearby",
            return_value={
                "stations": [
                    {
                        "station_id": "ev_1",
                        "name": "EV",
                        "latitude": 40.0,
                        "longitude": -80.0,
                    }
                ]
            },
        ),
    ):
        await _get_station_list(hass, {CONF_POSTAL: "12345"}, flow_id="flow_new")
        assert len(coord_cache) == 41  # 50 - 10 popped + 1 added


async def test_get_nearby_brands_and_stations_failures(hass):
    """Test _get_nearby_brands_and_stations failure paths."""
    # Falsy postal, uses home coords
    hass.config.latitude = 41.8781
    hass.config.longitude = -87.6298
    with patch(
        "py_gasbuddy.GasBuddy.price_lookup_service", return_value={"results": []}
    ) as mock_lookup:
        res = await _get_nearby_brands_and_stations(hass, None, None, 15)
        mock_lookup.assert_called_once_with(lat=41.8781, lon=-87.6298, zipcode=None, limit=20)
        assert res == ({}, {})

    # CSRFTokenMissing raises CloudflareBlocked
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup_service", side_effect=CSRFTokenMissing),
        pytest.raises(CloudflareBlocked),
    ):
        await _get_nearby_brands_and_stations(hass, "12345", None, 15)

    # APIError with cf_last=True raises CloudflareBlocked
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup_service", side_effect=APIError),
        patch(
            "custom_components.gasbuddy.config_flow._csrf_blocked_via_state",
            return_value=True,
        ),
        pytest.raises(CloudflareBlocked),
    ):
        await _get_nearby_brands_and_stations(hass, "12345", None, 15)

    # APIError with cf_last=False returns empty dicts
    with (
        patch("py_gasbuddy.GasBuddy.price_lookup_service", side_effect=APIError),
        patch(
            "custom_components.gasbuddy.config_flow._csrf_blocked_via_state",
            return_value=False,
        ),
    ):
        assert await _get_nearby_brands_and_stations(hass, "12345", None, 15) == ({}, {})

    # Generic exception returns empty dicts
    with patch(
        "py_gasbuddy.GasBuddy.price_lookup_service",
        side_effect=ValueError("Unexpected"),
    ):
        assert await _get_nearby_brands_and_stations(hass, "12345", None, 15) == ({}, {})

    # Station ID is missing or station brand parsing
    with patch(
        "py_gasbuddy.GasBuddy.price_lookup_service",
        return_value={
            "results": [
                {"station_id": None, "id": None},
                {
                    "station_id": "123",
                    "name": "Station 1",
                    "address": {"line1": "Road 1"},
                    "brands": [{"brandId": "b1", "name": "Brand 1"}],
                },
            ]
        },
    ):
        brands, stations = await _get_nearby_brands_and_stations(hass, "12345", None, 15)
        assert brands == {"b1": "Brand 1"}
        assert stations == {"123": "Station 1 (Road 1)"}


async def test_get_schema_options_user_input_none(hass):
    """Test _get_schema_options with None user_input."""
    schema = _get_schema_options(hass, None, {CONF_INTERVAL: 1800, CONF_UOM: True, CONF_GPS: False})
    assert schema is not None


async def test_subentry_flow_is_new(hass):
    """Test _is_new property of GasBuddySubentryFlowHandler."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    # Get the actual flow handler instance
    handler = hass.config_entries.subentries._progress[result["flow_id"]]  # noqa: SLF001
    assert handler._is_new is True  # noqa: SLF001


async def test_subentry_flow_manual_cloudflare(hass):
    """Test manual station flow with Cloudflare block and other validation errors."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
    )

    # Cloudflare block validation error
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Test"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "cloudflare"

    # InvalidStation exception validation error
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=InvalidStation,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Test"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "station_id"

    # Non-dict True returns (ev_charging = False fallback)
    with patch("custom_components.gasbuddy.config_flow.validate_station", return_value=True):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Test"},
        )
        assert res["type"] == FlowResultType.CREATE_ENTRY
        assert res["data"][CONF_EV_CHARGING] is False


async def test_subentry_flow_search_failed_home_postal(hass):
    """Test search failed scenarios in home2 and postal flows."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # Home2 SearchFailed
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "home"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "home"

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        side_effect=SearchFailed,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["step_id"] == "home2"
        assert res["errors"][CONF_STATION_ID] == "no_results"

    # Invalid postal validation
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "postal"},
    )
    res = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_POSTAL: "invalid!"},
    )
    assert res["type"] == FlowResultType.FORM
    assert res["errors"][CONF_POSTAL] == "invalid_postal"

    # Station list SearchFailed
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        side_effect=SearchFailed,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_POSTAL: "12345"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "no_results"


async def test_cheapest_flow_edge_cases(hass):
    """Test cheapest gas tracker flow edge cases (invalid postal, cloudflare, caching)."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "cheapest"},
    )

    # Invalid postal input in cheapest
    res = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Cheapest",
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_POSTAL: "invalid!",
        },
    )
    assert res["type"] == FlowResultType.FORM
    assert res["errors"][CONF_POSTAL] == "invalid_postal"

    # CloudflareBlocked in cheapest filters
    with patch(
        "custom_components.gasbuddy.config_flow._get_nearby_brands_and_stations",
        side_effect=CloudflareBlocked,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Cheapest",
                CONF_FUEL_KEY: "regular_gas",
                CONF_PRICE_TYPE: "best",
                CONF_POSTAL: "12345",
            },
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_SOLVER] == "cloudflare"

    # Complete cheapest filters flow successfully with postal caching
    with patch(
        "custom_components.gasbuddy.config_flow._get_nearby_brands_and_stations",
        return_value=({"b1": "Brand 1"}, {"s1": "Station 1"}),
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Cheapest",
                CONF_FUEL_KEY: "regular_gas",
                CONF_PRICE_TYPE: "best",
                CONF_POSTAL: "12345",
            },
        )
        assert res["type"] == FlowResultType.FORM
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_EXCLUDE_BRANDS: ["b1"],
                CONF_INCLUDE_BRANDS: [],
                CONF_EXCLUDE_STATIONS: [],
                CONF_INCLUDE_STATIONS: [],
            },
        )
        assert res["type"] == FlowResultType.CREATE_ENTRY
        assert res["data"][CONF_POSTAL] == "12345"


async def test_reconfigure_cheapest_flow_edge_cases(hass):
    """Test reconfigure cheapest subentry flow edge cases."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # Setup cheapest subentry
    subentry = config_entries.ConfigSubentry(
        subentry_id="cheapest_station",
        data=MappingProxyType({
            CONF_NAME: "Cheapest Station",
            CONF_CHEAPEST: True,
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_POSTAL: "12345",
        }),
        subentry_type="station",
        title="Cheapest Station",
        unique_id="cheapest_station",
    )
    hass.config_entries.async_add_subentry(hub, subentry)

    # Initiate reconfigure
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "cheapest_station",
            "subentry_id": "cheapest_station",
        },
    )
    assert result["step_id"] == "reconfigure_cheapest"

    # Invalid postal input
    res = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Cheapest",
            CONF_FUEL_KEY: "midgrade_gas",
            CONF_PRICE_TYPE: "best",
            CONF_POSTAL: "invalid!",
        },
    )
    assert res["type"] == FlowResultType.FORM
    assert res["errors"][CONF_POSTAL] == "invalid_postal"

    # Valid postal but cloudflare blocked on next step
    with patch(
        "custom_components.gasbuddy.config_flow._get_nearby_brands_and_stations",
        side_effect=CloudflareBlocked,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "New Cheapest",
                CONF_FUEL_KEY: "midgrade_gas",
                CONF_PRICE_TYPE: "best",
                CONF_POSTAL: "54321",
            },
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_SOLVER] == "cloudflare"

    # Re-run step 1, clear postal
    with patch(
        "custom_components.gasbuddy.config_flow._get_nearby_brands_and_stations",
        return_value=({"b1": "Brand 1"}, {"s1": "Station 1"}),
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "New Cheapest No Postal",
                CONF_FUEL_KEY: "midgrade_gas",
                CONF_PRICE_TYPE: "best",
                CONF_POSTAL: "",
            },
        )
        assert res["step_id"] == "reconfigure_cheapest_filters"

        # Complete Step 2 successfully
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_EXCLUDE_BRANDS: [],
                CONF_INCLUDE_BRANDS: ["b1"],
                CONF_EXCLUDE_STATIONS: [],
                CONF_INCLUDE_STATIONS: [],
            },
        )
        assert res["type"] == FlowResultType.ABORT
        assert res["reason"] == "reconfigure_successful"
        # Verify subentry was updated
        updated_sub = hub.subentries[subentry.subentry_id]
        assert updated_sub.data[CONF_NAME] == "New Cheapest No Postal"
        assert CONF_POSTAL not in updated_sub.data
        assert updated_sub.data[CONF_INCLUDE_BRANDS] == ["b1"]


async def test_reconfigure_station_subentry_failures(hass):
    """Test reconfigure station subentry failures (CloudflareBlocked, InvalidStation, ev_charging=False)."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # Setup station subentry
    subentry = config_entries.ConfigSubentry(
        subentry_id="999001",
        data=MappingProxyType({
            CONF_STATION_ID: "999001",
            CONF_NAME: "Gas Station 1",
        }),
        subentry_type="station",
        title="Gas Station 1",
        unique_id="999001",
    )
    hass.config_entries.async_add_subentry(hub, subentry)

    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={
            "source": "reconfigure",
            "unique_id": "999001",
            "subentry_id": "999001",
        },
    )
    assert result["step_id"] == "reconfigure"

    # Cloudflare blocked
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999002", CONF_NAME: "New Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "cloudflare"

    # InvalidStation exception
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=InvalidStation,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999002", CONF_NAME: "New Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "station_id"

    # Return to last shown form (returns to manual if no station_list)
    handler = hass.config_entries.subentries._progress[result["flow_id"]]  # noqa: SLF001
    handler._station_list = {"999002": "Test Station"}  # noqa: SLF001
    with patch("custom_components.gasbuddy.config_flow.validate_station", return_value=False):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999002", CONF_NAME: "New Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["step_id"] == "reconfigure"

    # Non-dict True validate return (ev_charging = False)
    with patch("custom_components.gasbuddy.config_flow.validate_station", return_value=True):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999002", CONF_NAME: "New Costco"},
        )
        assert res["type"] == FlowResultType.ABORT
        assert res["reason"] == "reconfigure_successful"
        assert hub.subentries[subentry.subentry_id].data[CONF_EV_CHARGING] is False


async def test_options_flow_invalid_url(hass):
    """Test options flow solver validation with an invalid URL."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="hub",
        data={CONF_NAME: "Hub", CONF_SOLVER: "http://valid-solver.com"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    res = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Hub Name",
            CONF_SOLVER: "invalid_url_pattern",
            CONF_TIMEOUT: 15000,
            CONF_BRAND_ADJUSTMENTS: {},
        },
    )
    assert res["type"] == FlowResultType.FORM
    assert res["errors"][CONF_SOLVER] == "invalid_url"


async def test_validate_station_success_and_collision(hass):
    """Test validate_station normal success and distance collision check."""
    # Gas station success path
    with patch(
        "py_gasbuddy.GasBuddy.price_lookup",
        return_value={"latitude": 40.0, "longitude": -80.0},
    ):
        res = await validate_station(hass, 999001)
        assert res == {"type": "gas", "latitude": 40.0, "longitude": -80.0}

    # Station ID cannot be 'hub'
    with pytest.raises(InvalidStation, match="Station ID cannot be 'hub'"):
        await validate_station(hass, "hub")

    # Station ID collision check (distance > 1.0)
    with (
        patch(
            "py_gasbuddy.GasBuddy.price_lookup",
            return_value={"latitude": 40.0, "longitude": -80.0},
        ),
        patch("py_gasbuddy.GasBuddy.ev_stations_nearby", return_value={"stations": []}),
        pytest.raises(InvalidStation),
    ):
        await validate_station(hass, 999001, lat=10.0, lon=10.0)


async def test_search_flow_success_and_failures(hass):
    """Test search-based flows (home & postal) success and validation failure branches."""
    hub = MockConfigEntry(domain=DOMAIN, unique_id="hub", data={CONF_NAME: "Hub"})
    hub.add_to_hass(hass)

    # 1. Happy path home coordinates search subentry flow (gas station)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "home"},
    )
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999001": "Costco"},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["step_id"] == "home2"

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value={"type": "gas", "latitude": 40.0, "longitude": -80.0},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Costco"},
        )
        assert res["type"] == FlowResultType.CREATE_ENTRY
        assert res["data"][CONF_EV_CHARGING] is False

    # 2. Happy path postal code search subentry flow (EV station)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "postal"},
    )
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999002": "Tesla Charger"},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_POSTAL: "12345"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["step_id"] == "station_list"

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value={"type": "ev", "latitude": 40.0, "longitude": -80.0},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999002", CONF_NAME: "Tesla Charger"},
        )
        assert res["type"] == FlowResultType.CREATE_ENTRY
        assert res["data"][CONF_EV_CHARGING] is True

    # 3. Validation failures in search-based flows (hits try-except and not validate block in _async_validate_and_create_subentry)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "postal"},
    )
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999001": "Costco"},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_POSTAL: "12345"},
        )

    # Validation throws CloudflareBlocked
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "cloudflare"

    # Validation throws InvalidStation
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=InvalidStation,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "station_id"

    # Validation returns False
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=False,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["errors"][CONF_STATION_ID] == "station_id"

    # Validation returns False, and self._station_list is None/empty -> returns manual form
    handler = hass.config_entries.subentries._progress[result["flow_id"]]  # noqa: SLF001
    handler._station_list = None  # noqa: SLF001
    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=False,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999001", CONF_NAME: "Costco"},
        )
        assert res["type"] == FlowResultType.FORM
        assert res["step_id"] == "manual"

    # Happy path search flow with validate returning True (non-dict) -> ev_charging = False (hits line 1073)
    result = await hass.config_entries.subentries.async_init(
        (hub.entry_id, "station"),
        context={"source": "user"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "search"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "postal"},
    )
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"999003": "Chevron"},
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_POSTAL: "12345"},
        )

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
    ):
        res = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STATION_ID: "999003", CONF_NAME: "Chevron"},
        )
        assert res["type"] == FlowResultType.CREATE_ENTRY
        assert res["data"][CONF_EV_CHARGING] is False
