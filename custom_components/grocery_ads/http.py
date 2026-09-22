from __future__ import annotations

import logging

import requests
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .connectors.base import BROWSER_HEADERS
from .const import CONF_STORE_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)

FETCH_TIMEOUT = 15  # seconds

MEDIA_TYPE_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "image": "image/jpeg",
}


class GroceryAdsFlyerView(HomeAssistantView):
    """Proxies a flyer store's current flyer bytes.

    Flyer URLs (PDF/image) live on the store's own site, and several of
    those sites set X-Frame-Options/CSP frame-ancestors that refuse to be
    framed by anyone else's page — a Lovelace `iframe` card pointed
    straight at the store's URL (even via a redirect) gets blocked by the
    browser. Fetching the bytes here and serving them same-origin avoids
    that, since the iframe never navigates to the blocked third-party
    origin.

    Also gives the dashboard a stable per-store URL: flyer URLs are
    re-scraped weekly and change every run, but a static Lovelace `iframe`
    card's `url` is a static YAML value with no templating support.

    Unauthenticated on purpose: an `iframe`/`img` `src` navigation can't
    carry the frontend's bearer token, and the target is the store's own
    public marketing flyer anyway, so there's nothing here to protect.
    """

    url = "/api/grocery_ads/flyer/{store_type}"
    name = "api:grocery_ads:flyer"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, store_type: str) -> web.Response:
        domain_data = self.hass.data.get(DOMAIN, {})
        flyer = None
        for entry_id, entry_data in domain_data.items():
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.data.get(CONF_STORE_TYPE) != store_type:
                continue
            flyer = entry_data["coordinator"].data
            break

        if not flyer or not flyer.urls:
            return web.Response(status=404, text="No flyer available")

        try:
            upstream = await self.hass.async_add_executor_job(self._fetch, flyer.urls[0])
        except requests.RequestException as err:
            _LOGGER.warning("Fetching flyer for %s failed: %s", store_type, err)
            return web.Response(status=502, text="Flyer source unavailable")

        content_type = upstream.headers.get("Content-Type", "").split(";")[0].strip()
        if not content_type:
            content_type = MEDIA_TYPE_CONTENT_TYPES.get(flyer.media_type, "application/octet-stream")
        return web.Response(body=upstream.content, content_type=content_type)

    @staticmethod
    def _fetch(url: str) -> requests.Response:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        return response
