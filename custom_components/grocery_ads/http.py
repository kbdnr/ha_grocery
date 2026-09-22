from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONF_STORE_TYPE, DOMAIN


class GroceryAdsFlyerView(HomeAssistantView):
    """Redirects to a flyer store's current flyer URL.

    Flyer URLs (PDF/image) are re-scraped weekly and change every time, so a
    static Lovelace `iframe` card can't point at one directly. This gives
    the dashboard a stable per-store URL to embed instead, that always
    redirects to whatever the coordinator most recently found.

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
        for entry_id, entry_data in domain_data.items():
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.data.get(CONF_STORE_TYPE) != store_type:
                continue
            flyer = entry_data["coordinator"].data
            if flyer and flyer.urls:
                raise web.HTTPFound(flyer.urls[0])
            break

        return web.Response(status=404, text="No flyer available")
