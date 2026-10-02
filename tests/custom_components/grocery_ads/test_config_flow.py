from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow

from custom_components.grocery_ads.const import DOMAIN

RANCH99_LOCATIONS = {"1007": "Arcadia, CA", "1693": "Beaverton, OR", "2222": "Test, CA"}


@pytest.fixture(autouse=True)
def ranch99_store_list():
    with patch(
        "custom_components.grocery_ads.connectors.ranch99.Ranch99Connector.list_locations",
        return_value=RANCH99_LOCATIONS,
    ) as mock:
        yield mock


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
async def test_99ranch_offers_its_stores_by_name_then_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "store"
    assert result["data_schema"].schema["location_id"].container == RANCH99_LOCATIONS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "1693"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "99 Ranch Market (Beaverton, OR)"
    assert result["data"] == {"store_type": "99ranch", "location_id": "1693"}


@pytest.mark.asyncio
async def test_99ranch_falls_back_to_typed_store_number_when_list_fails(hass, ranch99_store_list):
    import requests

    ranch99_store_list.side_effect = requests.ConnectionError("refused")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "store_number"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "  "}
    )
    assert result["errors"] == {"location_id": "invalid_store_number"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": " 1693 "}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "99 Ranch Market (1693)"
    assert result["data"] == {"store_type": "99ranch", "location_id": "1693"}


@pytest.mark.asyncio
async def test_asian_family_market_offers_its_four_stores(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "asian_family_market"}
    )
    assert result["step_id"] == "store"
    assert result["data_schema"].schema["location_id"].container == {
        "OR": "Beaverton, OR",
        "Bellevue": "Bellevue, WA",
        "Seattle": "Seattle, WA",
        "Tukwila": "Tukwila, WA",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "OR"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Asian Family Market (Beaverton, OR)"
    assert result["data"] == {"store_type": "asian_family_market", "location_id": "OR"}


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


async def _start_mealie_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "mealie"}
    )


@pytest.mark.asyncio
async def test_mealie_asks_for_url_and_token_then_creates_entry(hass):
    result = await _start_mealie_step(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "mealie"

    with patch(
        "custom_components.grocery_ads.config_flow.MealieClient.group_slug", return_value="home"
    ), patch("custom_components.grocery_ads.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://mealie.example.com/", "token": "secret"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mealie (recipes on sale)"
    assert result["data"] == {
        "store_type": "mealie", "url": "https://mealie.example.com", "token": "secret",
    }


@pytest.mark.asyncio
async def test_mealie_bad_token_shows_invalid_auth(hass):
    import requests

    response = requests.Response()
    response.status_code = 401
    result = await _start_mealie_step(hass)

    with patch(
        "custom_components.grocery_ads.config_flow.MealieClient.group_slug",
        side_effect=requests.HTTPError(response=response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://mealie.example.com", "token": "wrong"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "mealie"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_mealie_unreachable_shows_cannot_connect(hass):
    import requests

    result = await _start_mealie_step(hass)

    with patch(
        "custom_components.grocery_ads.config_flow.MealieClient.group_slug",
        side_effect=requests.ConnectionError("refused"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://mealie.example.com", "token": "secret"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


COSTCO_FETCH = "custom_components.grocery_ads.connectors.costco.CostcoConnector.fetch"


async def _start_costco_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "costco"}
    )


@pytest.mark.asyncio
async def test_costco_asks_for_postal_code(hass):
    result = await _start_costco_step(hass)
    assert result["step_id"] == "postal_code"
    assert result["description_placeholders"] == {"store": "Costco"}

    with patch(COSTCO_FETCH, return_value=[object()]), patch(
        "custom_components.grocery_ads.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_id": " 97005 "}
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Costco (97005)"
    assert result["data"] == {"store_type": "costco", "location_id": "97005"}


@pytest.mark.asyncio
@pytest.mark.parametrize("postal_code", ["9700", "970055", "abcde", "V6B 1A1"])
async def test_postal_code_must_be_five_digits(hass, postal_code):
    result = await _start_costco_step(hass)

    with patch(COSTCO_FETCH) as fetch:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_id": postal_code}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "postal_code"
    assert result["errors"] == {"location_id": "invalid_postal_code"}
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_postal_code_with_no_ad_is_rejected(hass):
    result = await _start_costco_step(hass)

    with patch(COSTCO_FETCH, return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_id": "99950"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"location_id": "no_ad_found"}


@pytest.mark.asyncio
async def test_postal_code_check_unreachable_shows_cannot_connect(hass):
    import requests

    result = await _start_costco_step(hass)

    with patch(COSTCO_FETCH, side_effect=requests.ConnectionError("refused")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_id": "97005"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


def test_every_form_field_and_error_has_a_label():
    import json
    import re
    from pathlib import Path

    import custom_components.grocery_ads as integration

    root = Path(integration.__file__).parent
    config = json.loads((root / "translations" / "en.json").read_text())["config"]
    source = (root / "config_flow.py").read_text()

    for step_id in re.findall(r'step_id="(\w+)"', source):
        assert config["step"][step_id]["data"], step_id
    for error in re.findall(r'= "(\w+)"\n', source):
        assert error in config["error"], error
