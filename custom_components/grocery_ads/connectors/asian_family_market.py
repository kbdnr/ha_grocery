import json
from datetime import date, datetime
import requests
from .base import FlyerConnector
from ..schema import FlyerRef

# Asian Family Market's site runs on the "base44" app-builder platform and
# exposes its weekly-ad posters through a public JSON entity API -- no auth,
# no Cloudflare bot-blocking observed (confirmed 2026-09-21). Ad content
# differs per physical store (Bellevue, Seattle, Tukwila, Beaverton), passed
# via the `store` query filter; note the Beaverton location's data is filed
# under the code "OR", not "Beaverton" -- confirmed by cross-referencing the
# API's own StoreQuickLink listing against HomepageWeeklyAd records.
APP_ID = "699266c8c2f2e91c54efa8af"
ENTITY_URL = f"https://asianfamilymkt.com/api/apps/{APP_ID}/entities/HomepageWeeklyAd"
DEFAULT_LOCATION_ID = "OR"  # Beaverton, OR


class AsianFamilyMarketConnector(FlyerConnector):
    store_id = "asian_family_market"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> FlyerRef | None:
        params = {
            "q": json.dumps({"status": "published", "store": self.location_id}),
            "sort": "-start_date",
            "limit": "1",
        }
        resp = requests.get(ENTITY_URL, params=params, timeout=15)
        resp.raise_for_status()
        records = resp.json()
        if not records:
            return None

        return self._parse_record(records[0])

    def _parse_record(self, record: dict) -> FlyerRef | None:
        posters = sorted(
            record.get("posters", []), key=lambda p: p.get("display_order", 0)
        )
        urls = [p["image_url"] for p in posters if p.get("image_url")]
        if not urls:
            return None

        try:
            valid_from = date.fromisoformat(record["start_date"])
            valid_to = date.fromisoformat(record["end_date"])
        except (KeyError, TypeError, ValueError):
            valid_from = valid_to = date.today()

        return FlyerRef(
            store=self.store_id,
            urls=urls,
            media_type="image",
            valid_from=valid_from,
            valid_to=valid_to,
            scraped_at=datetime.now(),
        )
