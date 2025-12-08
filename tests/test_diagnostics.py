"""Test gasbuddy diagnostics."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import DOMAIN
from custom_components.gasbuddy.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from tests.const import CONFIG_DATA

pytestmark = pytest.mark.asyncio


async def test_diagnostics(
    hass: HomeAssistant,
    mock_gasbuddy,
    mock_aioclient,
) -> None:
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gas Station",
        data=CONFIG_DATA,
        version=6,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Test Config Entry Diagnostics
    config_diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert config_diagnostics["config"]["data"]["station_id"] == 208656
    assert config_diagnostics["config"]["title"] == "Gas Station"

    # Test Device Diagnostics
    device_registry = dr.async_get(hass)
    # The integration registers devices via connections, not identifiers
    device = device_registry.async_get_device(connections={(DOMAIN, entry.entry_id)})
    assert device is not None

    device_diagnostics = await async_get_device_diagnostics(hass, entry, device)
    assert device_diagnostics["station_id"] == "208656"
    assert device_diagnostics["unit_of_measure"] == "dollars_per_gallon"
    assert device_diagnostics["regular_gas"]["price"] == 2.95