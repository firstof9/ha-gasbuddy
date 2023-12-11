"""Test config flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult, FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import (
    CONF_INTERVAL,
    CONF_NAME,
    CONF_POSTAL,
    CONF_STATION_ID,
    DEFAULT_NAME,
    DOMAIN,
)
from tests.const import CONFIG_DATA, STATION_LIST

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "input,step_id,title,data",
    [
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_STATION_ID: "208656",
            },
            "user",
            "gas_station",
            {
                CONF_NAME: "gas_station",
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
            },
        ),
    ],
)
async def test_form_home(
    input,
    step_id,
    title,
    data,
    hass,
    mock_gasbuddy,
):
    """Test we get the form."""
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
            result["flow_id"], {"next_step_id": "search"}
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "home"}
        )

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
    "input,input2,title,data",
    [
        (
            {
                CONF_POSTAL: "85396",
            },
            {
                CONF_STATION_ID: "208656",
                CONF_NAME: DEFAULT_NAME,
            },
            "gas_station",
            {
                CONF_NAME: "gas_station",
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
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
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "custom_components.gasbuddy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "custom_components.gasbuddy.config_flow._get_station_list",
        return_value=STATION_LIST,
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
            },
            "user",
            "gas_station",
            {
                CONF_NAME: "gas_station",
                CONF_STATION_ID: "208656",
                CONF_INTERVAL: 3600,
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
    mock_gasbuddy,
):
    """Test we get the form."""
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
