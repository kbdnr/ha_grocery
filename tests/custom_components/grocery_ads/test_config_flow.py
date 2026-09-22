from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow

from custom_components.grocery_ads.const import DOMAIN


@pytest.mark.asyncio
async def test_user_step_shows_store_dropdown(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_hmart_creates_entry_without_location_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "hmart"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "H Mart"
    assert result["data"] == {"store_type": "hmart"}


@pytest.mark.asyncio
async def test_99ranch_asks_for_location_then_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "location"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "2222"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"store_type": "99ranch", "location_id": "2222"}


@pytest.mark.asyncio
async def test_hmart_twice_aborts_as_already_configured(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "hmart"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "hmart"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_99ranch_same_location_twice_aborts_as_already_configured(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "1007"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "1007"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_99ranch_different_locations_both_succeed(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "1007"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"store_type": "99ranch", "location_id": "1007"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "2222"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"store_type": "99ranch", "location_id": "2222"}
