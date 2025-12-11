"""Global fixtures for gasbuddy integration."""

from unittest.mock import patch

from aioresponses import aioresponses
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gasbuddy.const import DOMAIN
from tests.const import CONFIG_DATA, COORDINATOR_DATA, COORDINATOR_DATA_CAD


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


@pytest.fixture(name="integration")
async def integration_fixture(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(domain=DOMAIN, title="gas_station", data=CONFIG_DATA, version=2)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
