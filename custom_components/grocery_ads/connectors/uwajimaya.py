import re
from datetime import date, datetime, timedelta
import requests
from bs4 import BeautifulSoup
from . import flipp
from .base import BROWSER_HEADERS, BaseConnector, FlyerConnector
from ..schema import AdItem, FlyerRef

WEEKLY_AD_PAGE = "https://www.uwajimaya.com/weekly-specials/"
# Uwajimaya's own site only has the PDF, but Flipp indexes the same weekly
# ad item by item (confirmed 2026-10-01), so the store gets both: items from
# Flipp via UwajimayaItemsConnector, and the PDF from UwajimayaConnector.
MERCHANT_NAME = "Uwajimaya"
DEFAULT_LOCATION_ID = "97005"  # Beaverton, OR
_FILENAME_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2})")


class UwajimayaConnector(FlyerConnector):
    store_id = "uwajimaya"

    def fetch(self) -> FlyerRef | None:
        resp = requests.get(WEEKLY_AD_PAGE, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return self._parse_page(resp.text)

    def _parse_page(self, html: str) -> FlyerRef | None:
        soup = BeautifulSoup(html, "html.parser")
        link = soup.select_one("div.section-button a.button-bar[href$='.pdf']")
        if not link or not link.get("href"):
            return None
        pdf_url = link["href"]

        valid_from = self._parse_date_from_filename(pdf_url) or date.today()
        valid_to = valid_from + timedelta(days=6)

        return FlyerRef(
            store=self.store_id,
            urls=[pdf_url],
            media_type="pdf",
            valid_from=valid_from,
            valid_to=valid_to,
            scraped_at=datetime.now(),
        )

    @staticmethod
    def _parse_date_from_filename(url: str) -> date | None:
        match = _FILENAME_DATE_RE.search(url)
        if not match:
            return None
        month, day, year = (int(g) for g in match.groups())
        try:
            return date(2000 + year, month, day)
        except ValueError:
            return None


class UwajimayaItemsConnector(BaseConnector):
    store_id = "uwajimaya"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> list[AdItem]:
        return flipp.fetch_ad_items(MERCHANT_NAME, self.store_id, self.location_id)
