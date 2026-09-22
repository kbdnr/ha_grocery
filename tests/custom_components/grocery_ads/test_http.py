from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocery_ads.const import CONF_STORE_TYPE, DOMAIN
from custom_components.grocery_ads.http import GroceryAdsFlyerView
from custom_components.grocery_ads.schema import FlyerRef


def _flyer(urls: list[str]) -> FlyerRef:
    return FlyerRef(
        store="uwajimaya",
        urls=urls,
        media_type="pdf",
        valid_from=date(2026, 9, 16),
        valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


def _register(hass, store_type: str, flyer: FlyerRef | None) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STORE_TYPE: store_type})
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.data = flyer
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}


@pytest.mark.asyncio
async def test_get_redirects_to_current_flyer_url(hass):
    _register(hass, "uwajimaya", _flyer(["https://example.com/flyer.pdf"]))
    view = GroceryAdsFlyerView(hass)

    with pytest.raises(web.HTTPFound) as exc_info:
        await view.get(MagicMock(), "uwajimaya")

    assert exc_info.value.headers["Location"] == "https://example.com/flyer.pdf"


@pytest.mark.asyncio
async def test_get_returns_404_when_no_matching_store(hass):
    _register(hass, "uwajimaya", _flyer(["https://example.com/flyer.pdf"]))
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "new_seasons")

    assert response.status == 404


@pytest.mark.asyncio
async def test_get_returns_404_when_flyer_has_no_urls_yet(hass):
    _register(hass, "uwajimaya", _flyer([]))
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "uwajimaya")

    assert response.status == 404


@pytest.mark.asyncio
async def test_get_returns_404_when_domain_has_no_entries(hass):
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "uwajimaya")

    assert response.status == 404
