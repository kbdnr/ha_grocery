from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
import responses as rsps_lib

from custom_components.grocery_ads.const import CONF_STORE_TYPE, DOMAIN
from custom_components.grocery_ads.http import GroceryAdsFlyerView
from custom_components.grocery_ads.schema import FlyerRef
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _flyer(urls: list[str], media_type: str = "pdf") -> FlyerRef:
    return FlyerRef(
        store="uwajimaya",
        urls=urls,
        media_type=media_type,
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
@rsps_lib.activate
async def test_get_proxies_current_flyer_bytes(hass):
    rsps_lib.add(
        rsps_lib.GET,
        "https://example.com/flyer.pdf",
        body=b"%PDF-1.4 fake bytes",
        status=200,
        headers={"Content-Type": "application/pdf; charset=binary"},
    )
    _register(hass, "uwajimaya", _flyer(["https://example.com/flyer.pdf"]))
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "uwajimaya")

    assert response.status == 200
    assert response.content_type == "application/pdf"
    assert response.body == b"%PDF-1.4 fake bytes"


@pytest.mark.asyncio
@rsps_lib.activate
async def test_get_falls_back_to_media_type_when_upstream_has_no_content_type(hass):
    rsps_lib.add(
        rsps_lib.GET,
        "https://example.com/flyer.jpg",
        body=b"fake image bytes",
        status=200,
        content_type=None,
    )
    _register(hass, "uwajimaya", _flyer(["https://example.com/flyer.jpg"], media_type="image"))
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "uwajimaya")

    assert response.status == 200
    assert response.content_type == "image/jpeg"


@pytest.mark.asyncio
@rsps_lib.activate
async def test_get_returns_502_when_upstream_fetch_fails(hass):
    rsps_lib.add(
        rsps_lib.GET,
        "https://example.com/flyer.pdf",
        status=500,
    )
    _register(hass, "uwajimaya", _flyer(["https://example.com/flyer.pdf"]))
    view = GroceryAdsFlyerView(hass)

    response = await view.get(MagicMock(), "uwajimaya")

    assert response.status == 502


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
