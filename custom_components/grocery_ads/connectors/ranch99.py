import json
import re
from datetime import date, datetime
import requests
from .base import BROWSER_HEADERS, FlyerConnector
from ..schema import FlyerRef

# 99 Ranch has no national weekly ad — deals vary per physical store. Full
# zip->store lookup is out of scope (see CLAUDE.md future work); the config
# flow just asks for the numeric store ID directly.
DEFAULT_LOCATION_ID = "1007"
PROMOTIONS_URL_TEMPLATE = "https://www.99ranch.com/stores/promotions/{location_id}"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
    re.S,
)
_DATE_RANGE_RE = re.compile(r"([A-Za-z]+)\.(\d{1,2})\s*-\s*([A-Za-z]+)\.(\d{1,2})")


class Ranch99Connector(FlyerConnector):
    store_id = "99ranch"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> FlyerRef | None:
        url = PROMOTIONS_URL_TEMPLATE.format(location_id=self.location_id)
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return self._parse_page(resp.text)

    def _parse_page(self, html: str) -> FlyerRef | None:
        match = _NEXT_DATA_RE.search(html)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        activities = (
            data.get("props", {})
            .get("pageProps", {})
            .get("detail", {})
            .get("storeActivities", [])
        )
        urls = [a["imageUrl"] for a in activities if a.get("imageUrl")]
        if not urls:
            return None

        valid_from, valid_to = self._widest_date_range(activities)
        return FlyerRef(
            store=self.store_id,
            urls=urls,
            media_type="image",
            valid_from=valid_from,
            valid_to=valid_to,
            scraped_at=datetime.now(),
        )

    @classmethod
    def _widest_date_range(cls, activities: list[dict]) -> tuple[date, date]:
        today = date.today()
        froms, tos = [], []
        for activity in activities:
            parsed = cls._parse_date_range(activity.get("date", ""), today.year)
            if parsed:
                froms.append(parsed[0])
                tos.append(parsed[1])
        if not froms:
            return today, today
        return min(froms), max(tos)

    @staticmethod
    def _parse_date_range(text: str, year: int) -> tuple[date, date] | None:
        match = _DATE_RANGE_RE.match(text.strip())
        if not match:
            return None
        start_mon, start_day, end_mon, end_day = match.groups()
        try:
            start = datetime.strptime(f"{start_mon} {start_day} {year}", "%b %d %Y").date()
            end = datetime.strptime(f"{end_mon} {end_day} {year}", "%b %d %Y").date()
        except ValueError:
            return None
        if end < start:
            end = end.replace(year=year + 1)
        return start, end
