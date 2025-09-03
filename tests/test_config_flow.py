"""Test config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_GPS,
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_SOLVER,
    CONF_STATION_ID,
    CONF_UOM,
    DEFAULT_NAME,
    DOMAIN,
)
from tests.common import load_fixture
from tests.const import CONFIG_DATA, STATION_LIST

BASE_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"
HOSTNAME_SOLVER_URL = "http://flaresolverr:8191/v1"
NO_STATIONS_LIST = {"-": "No stations in search area."}

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "input,input2,step_id,title,data",
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
                CONF_GPS: True,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_SOLVER: SOLVER_URL,
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input2
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input,input2,step_id,title,data",
    [
        (
            {
                CONF_SOLVER: HOSTNAME_SOLVER_URL,
            },
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "user",
            DEFAULT_NAME,
            {
                CONF_GPS: True,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_SOLVER: HOSTNAME_SOLVER_URL,
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
        status=200,
        body=load_fixture("location_results.json"),
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input2
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input,input2,title,data",
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_list"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input2
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input,step_id,title,data",
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
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_GPS: True,
                CONF_SOLVER: SOLVER_URL,
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

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input,input2,step_id,title,data",
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home2"
        assert result["errors"] == {"station_id": "no_results"}


@pytest.mark.parametrize(
    "input,input2,title,data",
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "station_list"
        assert result["errors"] == {"station_id": "no_results"}


@pytest.mark.parametrize(
    "input,step_id",
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "home"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    "input,step_id",
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "postal"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    "input,step_id",
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

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ), patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {CONF_SOLVER: "invalid_url"}


@pytest.mark.parametrize(
    "input,step_id,title,data",
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

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ), patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
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
    "input,step_id,title,data",
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

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ), patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
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
    "input,step_id,title,data",
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
    "input,step_id,title,data",
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

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ), patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
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
    entry = MockConfigEntry(
        domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2
    )

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
    "input,step_id,title,data",
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
                CONF_GPS: True,
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
                CONF_UOM: True,
                CONF_SOLVER: "",
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

    with patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
    ), patch(
        "custom_components.gasbuddy.config_flow.validate_station",
        return_value=True,
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
    "input,data",
    [
        (
            {
                CONF_INTERVAL: 1600,
                CONF_UOM: True,
                CONF_GPS: True,
            },
            {
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
    entry = MockConfigEntry(
        domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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
