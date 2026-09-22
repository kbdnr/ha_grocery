import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ discoverable by the `hass` fixture.

    pytest-homeassistant-custom-component only looks at Home Assistant's
    built-in integrations unless a test opts in via the
    `enable_custom_integrations` fixture. This applies it automatically to
    every test under tests/custom_components/ so individual test modules
    don't each need to request it.
    """
    yield
