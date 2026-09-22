import re
from datetime import date, datetime, timedelta
import requests
from .base import BROWSER_HEADERS, FlyerConnector
from ..schema import FlyerRef

# This redirect endpoint is a stable WordPress page slug that always 301s to
# the current week's dated PDF -- no HTML scraping needed, just follow it.
WEEKLY_SPECIALS_REDIRECT = "https://marketofchoice.com/download-weekly-specials"
_FILENAME_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})-MoC-Weekly-Specials")


class MarketOfChoiceConnector(FlyerConnector):
    store_id = "market_of_choice"

    def fetch(self) -> FlyerRef | None:
        resp = requests.get(WEEKLY_SPECIALS_REDIRECT, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        pdf_url = resp.url
        if not pdf_url.lower().endswith(".pdf"):
            return None

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
        year, month, day = (int(g) for g in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
