"""Test config flow."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from aioresponses import CallbackResult
from py_gasbuddy.exceptions import APIError, CSRFTokenMissing, MissingSearchData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.config_flow import (
    CloudflareBlocked,
    InvalidStation,
    SearchFailed,
    _csrf_blocked_via_state,  # noqa: PLC2701
    _get_station_list,  # noqa: PLC2701
    validate_station,
)
from custom_components.gasbuddy.const import (
    CONF_CHEAPEST,
    CONF_EV_CHARGING,
    CONF_FETCH_GAS,
    CONF_FUEL_KEY,
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_PRICE_TYPE,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_TIMEOUT,
    CONF_UOM,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant import config_entries, setup
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from tests.common import load_fixture
from tests.const import CONFIG_DATA, STATION_LIST

BASE_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"
HOSTNAME_SOLVER_URL = "http://flaresolverr:8191/v1"
NO_STATIONS_LIST = {"-": "No stations in search area."}
EXPECTED_STATION_COORDS = {
    "latitude": 44.019263,
    "longitude": -92.457476,
}


def gb_graphql_callback(url, **kwargs):
    """Return mock responses for the GasBuddy GraphQL API based on operationName."""
    payload = kwargs.get("json") or json.loads(kwargs.get("data", "{}"))
    op = payload.get("operationName")
    if op == "LocationBySearchTerm":
        return CallbackResult(status=200, body=load_fixture("location_results.json"))
    if op == "GetStation":
        return CallbackResult(status=200, body=load_fixture("station.json"))
    if op == "EvStationsSearch":
        return CallbackResult(
            status=200,
            payload={"data": {"evStationsNearby": {"stations": [], "total": 0, "limit": 20}}},
        )
    raise AssertionError(f"Unhandled GraphQL operationName in test callback: {op!r}")


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("input", "input2", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: SOLVER_URL,
            },
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_home(
    input,
    input2,
    step_id,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        callback=gb_graphql_callback,
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input2)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **data,
            **EXPECTED_STATION_COORDS,
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input", "input2", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: HOSTNAME_SOLVER_URL,
            },
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
                CONF_SOLVER: HOSTNAME_SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_home_hostname_solver(
    input,
    input2,
    step_id,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test form with hostname-based solver URL."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        callback=gb_graphql_callback,
        repeat=True,
    )
    mock_aioclient.post(
        HOSTNAME_SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input2)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **data,
            **EXPECTED_STATION_COORDS,
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input", "input2", "title", "data"),
    [
        (
            {
                CONF_POSTAL: "85396",
                CONF_SOLVER: SOLVER_URL,
            },
            {
                CONF_STATION_ID: "32394",
                CONF_NAME: DEFAULT_NAME,
            },
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_postal(
    input,
    input2,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        callback=gb_graphql_callback,
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "postal"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM

        assert result["step_id"] == "postal"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_list"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input2)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **data,
            **EXPECTED_STATION_COORDS,
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: SOLVER_URL,
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_manual(
    input,
    step_id,
    title,
    data,
    hass,
    mock_aioclient,
    mock_gasbuddy,
):
    """Test we get the form."""
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("station.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with (
        patch(
            "custom_components.gasbuddy.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **data,
            **EXPECTED_STATION_COORDS,
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input", "input2", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: SOLVER_URL,
            },
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_GPS: True,
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_home_no_stations(
    input,
    input2,
    step_id,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("no_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result["errors"] == {"station_id": "no_results"}


@pytest.mark.parametrize(
    ("input", "input2", "title", "data"),
    [
        (
            {
                CONF_POSTAL: "85396",
                CONF_SOLVER: SOLVER_URL,
            },
            {
                CONF_STATION_ID: "208656",
                CONF_NAME: DEFAULT_NAME,
            },
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_GPS: True,
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_postal_no_stations(
    input,
    input2,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("no_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "postal"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM

        assert result["step_id"] == "postal"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_list"
        assert result["errors"] == {"station_id": "no_results"}


@pytest.mark.parametrize(
    ("input", "step_id"),
    [
        (
            {
                CONF_SOLVER: "invalid.url",
            },
            "user",
        ),
    ],
)
async def test_form_home_invalid_url(
    input,
    step_id,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    ("input", "step_id"),
    [
        (
            {
                CONF_POSTAL: "85396",
                CONF_SOLVER: "invalid.url",
            },
            "user",
        ),
    ],
)
async def test_form_postal_invalid_url(
    input,
    step_id,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "postal"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "postal"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "postal"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    ("input", "step_id"),
    [
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: "invalid.url",
            },
            "user",
        ),
    ],
)
async def test_form_manual_invalid_url(
    input,
    step_id,
    hass,
    mock_aioclient,
    mock_gasbuddy,
):
    """Test we get the form."""
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == step_id

    with (
        patch(
            "custom_components.gasbuddy.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: SOLVER_URL,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "reconfigure",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure(
    input,
    step_id,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_aioclient,
    mock_gasbuddy,
) -> None:
    """Test reconfigure flow."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )

    entry = integration

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "gas", **EXPECTED_STATION_COORDS},
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == {
            **data,
            **EXPECTED_STATION_COORDS,
        }


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: "invalid.url",
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "reconfigure",
            DEFAULT_NAME,
            {
                CONF_GPS: True,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_invalid_url(
    input,
    step_id,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_aioclient,
    mock_gasbuddy,
) -> None:
    """Test reconfigure flow."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )

    entry = integration

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input,
        )

        assert result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: SOLVER_URL,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "reconfigure",
            DEFAULT_NAME,
            {
                CONF_GPS: True,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_invalid_station(
    input,
    step_id,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_aioclient,
    mock_gasbuddy,
) -> None:
    """Test reconfigure flow."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=401,
        body="Random Error",
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )

    entry = integration

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=False,
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input,
        )

        assert result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: SOLVER_URL,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "reconfigure",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: SOLVER_URL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_server_error(
    input,
    step_id,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_aioclient,
    mock_gasbuddy,
) -> None:
    """Test reconfigure flow."""
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

    entry = integration

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == data


@pytest.mark.parametrize(
    "input",
    [
        (
            {
                CONF_INTERVAL: 30,
                CONF_UOM: True,
                CONF_GPS: True,
            },
        ),
    ],
)
async def test_form_options_error(
    input,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
        repeat=True,
    )
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with pytest.raises(InvalidData):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=input
        )

    assert result["type"] is FlowResultType.FORM


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: "",
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "reconfigure",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: None,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_no_solver(
    input,
    step_id,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_aioclient,
    mock_gasbuddy,
) -> None:
    """Test reconfigure flow."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )

    entry = integration

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value={"type": "gas", **EXPECTED_STATION_COORDS},
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == step_id

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == {
            **data,
            **EXPECTED_STATION_COORDS,
        }


@pytest.mark.parametrize(
    ("input", "data"),
    [
        (
            {
                CONF_INTERVAL: 1600,
                CONF_UOM: True,
                CONF_GPS: True,
            },
            {
                CONF_EV_CHARGING: False,
                CONF_FETCH_GAS: True,
                CONF_GPS: True,
                CONF_INTERVAL: 1600,
                CONF_UOM: True,
            },
        ),
    ],
)
async def test_form_options(
    input,
    data,
    hass,
    integration,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test we get the form."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("location_results.json"),
        repeat=True,
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
        repeat=True,
    )
    entry = integration

    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=input
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == data
        await hass.async_block_till_done()

        assert entry.options.get(CONF_INTERVAL) == 1600
        mock_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("input", "input2", "step_id", "title", "data"),
    [
        (
            {
                CONF_SOLVER: "",  # Test empty string
            },
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
                CONF_SOLVER: "",
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_home_empty_solver(
    input,
    input2,
    step_id,
    title,
    data,
    hass,
    mock_gasbuddy,
    mock_aioclient,
):
    """Test the Home flow allows an empty solver URL."""
    # Mock responses for successful flow without solver
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        callback=gb_graphql_callback,
        repeat=True,
    )

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        # Select Search/Home path
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

        # Submit empty solver
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        # Verify we moved to the next step (home2) and didn't get an error
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result.get("errors") == {}  # Ensure no errors

        # Complete the flow
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input2)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **data,
            **EXPECTED_STATION_COORDS,
        }


@pytest.mark.parametrize(
    ("input", "step_id", "title", "data"),
    [
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: "",  # Test empty string
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_SOLVER: "",
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        ),
    ],
)
async def test_form_manual_empty_solver(
    input,
    step_id,
    title,
    data,
    hass,
    mock_aioclient,
    mock_gasbuddy,
):
    """Test the Manual flow allows an empty solver URL."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        BASE_URL,
        status=200,
        body=load_fixture("station.json"),
        repeat=True,
    )

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "custom_components.gasbuddy.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value=STATION_LIST,
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
    ):
        # Select Manual path
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        # Submit empty solver
        result = await hass.config_entries.flow.async_configure(result["flow_id"], input)

        # Verify entry creation without error
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data


async def test_validate_station_error(hass, mock_aioclient):
    """Test validate_station with error response."""

    with patch(
        "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
        return_value={"errors": ["test error"]},
    ):
        assert await validate_station(hass, 123) is False


async def test_form_manual_invalid_station(hass, mock_aioclient):
    """Test manual flow with invalid station."""
    with patch(
        "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
        return_value={"errors": ["test error"]},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "123",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


async def test_validate_station_api_error(hass):
    """Test validate_station raises InvalidStation on APIError."""
    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
            side_effect=APIError("test error"),
        ),
        pytest.raises(InvalidStation),
    ):
        await validate_station(hass, 123, None)


async def test_get_station_list_missing_data_error(hass):
    """Test _get_station_list raises SearchFailed on MissingSearchData."""
    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.location_search",
            side_effect=MissingSearchData("test error"),
        ),
        pytest.raises(SearchFailed),
    ):
        await _get_station_list(hass, {})


async def test_get_station_list_skips_null_station_id(hass):
    """Stations with station_id=None are silently skipped."""
    fake_results = {
        "results": [
            {"station_id": None, "name": "Bad Station", "address": {"line1": "1 Nowhere"}},
            {"station_id": "999001", "name": "Good Station", "address": {"line1": "100 Test Blvd"}},
        ]
    }
    with patch(
        "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.location_search",
        return_value=fake_results,
    ):
        result = await _get_station_list(hass, {})
    assert "999001" in result
    assert None not in result


async def test_form_manual_renders(hass):
    """Test manual flow renders the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_form_search_home_failed(hass):
    """Test search flow (home) handles SearchFailed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First enter the search menu
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    assert result["type"] is FlowResultType.MENU

    # Then enter the home search step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "home"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "home"

    # Submit the first home form to get to home2 step
    # Schema for home is solver and timeout
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        side_effect=SearchFailed,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOLVER: ""}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result["errors"] == {CONF_STATION_ID: "no_results"}


async def test_form_search_postal_failed(hass):
    """Test search flow (postal) handles SearchFailed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First enter the search menu
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    assert result["type"] is FlowResultType.MENU

    # Then enter the postal search step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "postal"

    # Submit postal code to get to station_list step
    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        side_effect=SearchFailed,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_POSTAL: "12345"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"
        assert result["errors"] == {CONF_STATION_ID: "no_results"}


async def test_reconfigure_invalid_station_exception(hass, integration):
    """Test reconfigure flow handles InvalidStation exception."""
    entry = integration

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=InvalidStation,
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "123",
                CONF_SOLVER: "",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


async def test_form_manual_invalid_station_exception(hass):
    """Test manual flow handles InvalidStation exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            side_effect=InvalidStation,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "123",
                CONF_SOLVER: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


async def test_manual_flow_trimming(hass):
    """Test manual flow trims spaces from input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STATION_ID: " 12345 ",
                CONF_NAME: " My Station ",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STATION_ID] == "12345"
    assert result["data"][CONF_NAME] == "My Station"


async def test_home2_invalid_station_exception(hass):
    """Test home2 flow handles InvalidStation exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "home"}
    )

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value={"32394": "Holiday @ 400 4th St SE"},
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            side_effect=InvalidStation,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOLVER: SOLVER_URL}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


async def test_home2_non_dict_validation(hass):
    """Test home2 flow handles non-dict validation return (ev_charging = False)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "home"}
    )

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"32394": "Holiday @ 400 4th St SE"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOLVER: SOLVER_URL}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"

    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
        patch(
            "custom_components.gasbuddy.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"][CONF_EV_CHARGING] is False


async def test_station_list_invalid_station_exception(hass):
    """Test station_list flow handles InvalidStation exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value={"32394": "Holiday @ 400 4th St SE"},
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            side_effect=InvalidStation,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_POSTAL: "55904",
                CONF_SOLVER: SOLVER_URL,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"
        assert result["errors"] == {CONF_STATION_ID: "station_id"}


async def test_station_list_non_dict_validation(hass):
    """Test station_list flow handles non-dict validation return (ev_charging = False)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value={"32394": "Holiday @ 400 4th St SE"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_POSTAL: "55904",
                CONF_SOLVER: SOLVER_URL,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"

    with (
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            return_value=True,
        ),
        patch(
            "custom_components.gasbuddy.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"][CONF_EV_CHARGING] is False


async def test_cheapest_flow_gps(hass):
    """Test cheapest gas tracker flow using home coordinates (no postal)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "cheapest"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "cheapest"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Cheapest Gas",
                CONF_POSTAL: "",
                CONF_FUEL_KEY: "regular_gas",
                CONF_PRICE_TYPE: "best",
                CONF_SOLVER: "",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Cheapest Gas"
        assert result["data"][CONF_CHEAPEST] is True
        assert result["data"][CONF_FUEL_KEY] == "regular_gas"
        assert result["data"][CONF_PRICE_TYPE] == "best"
        assert CONF_POSTAL not in result["data"]
        assert result["data"][CONF_SOLVER] is None
        assert result["options"][CONF_EV_CHARGING] is False
        assert result["options"][CONF_FETCH_GAS] is True

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_cheapest_flow_postal(hass):
    """Test cheapest gas tracker flow using postal code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "cheapest"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Cheapest Gas Near Me",
                CONF_POSTAL: "13201",
                CONF_FUEL_KEY: "premium_gas",
                CONF_PRICE_TYPE: "cash",
                CONF_SOLVER: "",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_CHEAPEST] is True
        assert result["data"][CONF_FUEL_KEY] == "premium_gas"
        assert result["data"][CONF_PRICE_TYPE] == "cash"
        assert result["data"][CONF_POSTAL] == "13201"


async def test_cheapest_flow_invalid_solver(hass):
    """Test cheapest flow rejects invalid solver URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cheapest"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cheapest"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Cheapest Gas",
            CONF_POSTAL: "",
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_SOLVER: "not-a-valid-url",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cheapest"
    assert result["errors"] == {CONF_SOLVER: "invalid_url"}


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_invalid_station_id_format(hass):
    r"""Manual flow rejects station IDs that don't match ^\d{1,20}$ (lines 451-452)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: DEFAULT_NAME, CONF_STATION_ID: "abc-not-numeric"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {CONF_STATION_ID: "station_id"}


@pytest.mark.asyncio
async def test_postal_invalid_format(hass):
    """Postal flow rejects postal codes that don't match the postal regex (lines 622-623)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_POSTAL: "NOTVALID"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "postal"
    assert result["errors"] == {CONF_POSTAL: "invalid_postal"}


@pytest.mark.asyncio
async def test_reconfigure_invalid_station_id_format(hass, integration):
    """Reconfigure rejects non-numeric station IDs (lines 781-782)."""
    entry = integration
    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert reconfigure_result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        {CONF_NAME: DEFAULT_NAME, CONF_STATION_ID: "abc-invalid", CONF_SOLVER: ""},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATION_ID: "station_id"}


@pytest.mark.asyncio
async def test_reconfigure_cheapest_show_form(hass):
    """Reconfigure for a cheapest entry shows the cheapest form (lines 775, 856)."""
    from tests.const import CONFIG_DATA_CHEAPEST, OPTIONS_CHEAPEST  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Gas",
        data=CONFIG_DATA_CHEAPEST,
        options=OPTIONS_CHEAPEST,
        version=2,
    )
    entry.add_to_hass(hass)

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"


@pytest.mark.asyncio
async def test_reconfigure_cheapest_success(hass):
    """Reconfigure cheapest entry with valid data succeeds (lines 823-850)."""
    from tests.const import CONFIG_DATA_CHEAPEST, OPTIONS_CHEAPEST  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Gas",
        data=CONFIG_DATA_CHEAPEST,
        options=OPTIONS_CHEAPEST,
        version=2,
    )
    entry.add_to_hass(hass)

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            {
                CONF_NAME: "Updated Cheapest",
                CONF_POSTAL: "90210",
                CONF_FUEL_KEY: "premium_gas",
                CONF_PRICE_TYPE: "cash",
                CONF_SOLVER: "",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_NAME] == "Updated Cheapest"
    assert entry.data[CONF_POSTAL] == "90210"


@pytest.mark.asyncio
async def test_reconfigure_cheapest_invalid_solver(hass):
    """Reconfigure cheapest entry rejects invalid solver URL (lines 828-829)."""
    from tests.const import CONFIG_DATA_CHEAPEST, OPTIONS_CHEAPEST  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Gas",
        data=CONFIG_DATA_CHEAPEST,
        options=OPTIONS_CHEAPEST,
        version=2,
    )
    entry.add_to_hass(hass)

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        {
            CONF_NAME: "Cheapest Gas",
            CONF_POSTAL: "",
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_SOLVER: "not-a-valid-url",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.asyncio
async def test_station_list_cache_eviction(hass):
    """Station coord cache evicts oldest entries when >= 50 flow IDs exist (lines 213-214)."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["station_coordinates_by_flow"] = {f"flow_{i}": {} for i in range(50)}

    ev_station = {
        "station_id": "ev001",
        "name": "Test EV",
        "street_address": "1 Main St",
        "latitude": 33.5,
        "longitude": -112.5,
    }
    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.location_search",
            return_value={"results": []},
        ),
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.ev_stations_nearby",
            return_value={"stations": [ev_station]},
        ),
    ):
        await _get_station_list(hass, {"lat": 33.5, "lon": -112.5}, "new_flow_id")

    cache = hass.data[DOMAIN]["station_coordinates_by_flow"]
    assert len(cache) == 41  # 50 - 10 evicted + 1 new


@pytest.mark.asyncio
async def test_reconfigure_cheapest_clears_postal(hass):
    """Reconfigure cheapest entry removes postal when submitted blank (line 843)."""
    from tests.const import CONFIG_DATA_CHEAPEST, OPTIONS_CHEAPEST  # noqa: PLC0415

    config_with_postal = {**CONFIG_DATA_CHEAPEST, CONF_POSTAL: "12345"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Gas",
        data=config_with_postal,
        options=OPTIONS_CHEAPEST,
        version=2,
    )
    entry.add_to_hass(hass)

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            {
                CONF_NAME: "Cheapest Gas",
                CONF_POSTAL: "",
                CONF_FUEL_KEY: "regular_gas",
                CONF_PRICE_TYPE: "best",
                CONF_SOLVER: "",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert CONF_POSTAL not in entry.data


@pytest.mark.asyncio
async def test_cheapest_flow_invalid_postal(hass):
    """Cheapest flow rejects a postal code that fails _POSTAL_RE validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cheapest"}
    )
    assert result["step_id"] == "cheapest"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Cheapest Gas",
            CONF_POSTAL: "NOTVALID",
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_SOLVER: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cheapest"
    assert result["errors"].get(CONF_POSTAL) == "invalid_postal"


@pytest.mark.asyncio
async def test_reconfigure_cheapest_invalid_postal(hass):
    """Reconfigure cheapest entry rejects invalid postal code."""
    from tests.const import CONFIG_DATA_CHEAPEST, OPTIONS_CHEAPEST  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Gas",
        data=CONFIG_DATA_CHEAPEST,
        options=OPTIONS_CHEAPEST,
        version=2,
    )
    entry.add_to_hass(hass)

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        {
            CONF_NAME: "Cheapest Gas",
            CONF_POSTAL: "NOTVALID",
            CONF_FUEL_KEY: "regular_gas",
            CONF_PRICE_TYPE: "best",
            CONF_SOLVER: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert CONF_POSTAL in result["errors"]


@pytest.mark.parametrize(
    ("cf_last", "blocked"),
    [
        (False, True),  # last round-trip failed the CSRF/Cloudflare check
        (None, False),  # never dispatched (e.g. mocked client) is not a block
        (True, False),  # last round-trip returned parseable JSON
    ],
)
async def test_csrf_blocked_via_state_signal(cf_last, blocked):
    """Only ``_cf_last is False`` counts as a block; ``None`` must not."""
    assert _csrf_blocked_via_state(SimpleNamespace(_cf_last=cf_last)) is blocked


async def test_csrf_blocked_via_state_missing_attr():
    """A client without ``_cf_last`` is treated as not blocked."""
    assert _csrf_blocked_via_state(SimpleNamespace()) is False


async def test_validate_station_cloudflare_blocked(hass):
    """Test validate_station raises CloudflareBlocked when the CSRF probe trips."""
    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
            side_effect=APIError("blocked"),
        ),
        patch(
            "custom_components.gasbuddy.config_flow._csrf_blocked_via_state",
            return_value=True,
        ),
        pytest.raises(CloudflareBlocked),
    ):
        await validate_station(hass, 123, None)


async def test_validate_station_csrf_token_missing(hass):
    """A propagated CSRFTokenMissing maps straight to CloudflareBlocked."""
    with (
        patch(
            "custom_components.gasbuddy.config_flow.py_gasbuddy.GasBuddy.price_lookup",
            side_effect=CSRFTokenMissing,
        ),
        pytest.raises(CloudflareBlocked),
    ):
        await validate_station(hass, 123, None)


async def test_reconfigure_cloudflare_blocked(hass, integration):
    """Reconfigure flow surfaces the cloudflare error on a CSRF block."""
    entry = integration

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "123",
                CONF_SOLVER: "",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_STATION_ID: "cloudflare"}


async def test_form_manual_cloudflare_blocked(hass):
    """Manual flow surfaces the cloudflare error on a CSRF block."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        side_effect=CloudflareBlocked,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "123",
                CONF_SOLVER: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {CONF_STATION_ID: "cloudflare"}


async def test_home2_cloudflare_blocked(hass):
    """home2 flow surfaces the cloudflare error on a CSRF block."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "home"}
    )

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value={"32394": "Holiday @ 400 4th St SE"},
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            side_effect=CloudflareBlocked,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOLVER: SOLVER_URL}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result["errors"] == {CONF_STATION_ID: "cloudflare"}


async def test_station_list_cloudflare_blocked(hass):
    """station_list flow surfaces the cloudflare error on a CSRF block."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "postal"}
    )

    with (
        patch(
            "custom_components.gasbuddy.config_flow._get_station_list",
            return_value={"32394": "Holiday @ 400 4th St SE"},
        ),
        patch(
            "custom_components.gasbuddy.config_flow.validate_station",
            side_effect=CloudflareBlocked,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_POSTAL: "55904",
                CONF_SOLVER: SOLVER_URL,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "32394",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station_list"
        assert result["errors"] == {CONF_STATION_ID: "cloudflare"}
