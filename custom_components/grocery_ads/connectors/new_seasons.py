import re
from datetime import date, datetime
import requests
from .base import BROWSER_HEADERS, FlyerConnector
from ..schema import FlyerRef

WEEKLY_AD_PAGE = "https://www.newseasonsmarket.com/weekly-ad"
_PDF_LINK_RE = re.compile(
    r'href="(https://www\.newseasonsmarket\.com/getContentAsset/[^"]+\.pdf[^"]*)"'
)
_DATE_RANGE_RE = re.compile(r"(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})")


class NewSeasonsConnector(FlyerConnector):
    store_id = "new_seasons"

    def fetch(self) -> FlyerRef | None:
        resp = requests.get(WEEKLY_AD_PAGE, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return self._parse_page(resp.text)

    def _parse_page(self, html: str) -> FlyerRef | None:
        match = _PDF_LINK_RE.search(html)
        if not match:
            return None
        pdf_url = match.group(1)
        valid_from, valid_to = self._parse_date_range(pdf_url)

        return FlyerRef(
            store=self.store_id,
            urls=[pdf_url],
            media_type="pdf",
            valid_from=valid_from,
            valid_to=valid_to,
            scraped_at=datetime.now(),
        )

    @staticmethod
    def _parse_date_range(url: str) -> tuple[date, date]:
        today = date.today()
        match = _DATE_RANGE_RE.search(url)
        if not match:
            return today, today
        m1, d1, y1, m2, d2, y2 = (int(g) for g in match.groups())
        try:
            start = date(2000 + y1, m1, d1)
            end = date(2000 + y2, m2, d2)
        except ValueError:
            return today, today
        return start, end
