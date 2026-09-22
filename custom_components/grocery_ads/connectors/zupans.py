import re
from datetime import date, datetime
import requests
from bs4 import BeautifulSoup
from .base import BROWSER_HEADERS, BaseConnector
from ..schema import AdItem

PROMOTIONS_API = "https://www.zupans.com/wp-json/wp/v2/promotions"
_PRICE_RE = re.compile(r"\$([\d]+\.[\d]{2})\s*([a-zA-Z]+)?")
_THROUGH_RE = re.compile(r"Through\s+([A-Za-z]+)\s+(\d{1,2})", re.IGNORECASE)


class ZupansConnector(BaseConnector):
    store_id = "zupans"

    def fetch(self) -> list[AdItem]:
        resp = requests.get(
            PROMOTIONS_API,
            params={"slug": "whats-on-sale"},
            headers=BROWSER_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return []
        return self._parse_promotion(data[0])

    def _parse_promotion(self, promotion: dict) -> list[AdItem]:
        html = promotion.get("content", {}).get("rendered", "")
        modified = promotion.get("modified", "")
        scraped_at = datetime.now()
        valid_from = scraped_at.date()
        valid_to = self._parse_valid_to(html, modified) or valid_from

        soup = BeautifulSoup(html, "html.parser")
        items = []
        for article in soup.find_all("article"):
            item = self._parse_article(article, valid_from, valid_to, scraped_at)
            if item:
                items.append(item)
        return items

    def _parse_article(self, article, valid_from, valid_to, scraped_at) -> AdItem | None:
        try:
            name_el = article.find("h3")
            price_el = article.find("p", class_="link")
            tags_el = article.find("p", class_="micro")
            if not name_el or not price_el:
                return None

            name = name_el.get_text(strip=True)
            price_match = _PRICE_RE.search(price_el.get_text(" ", strip=True))
            if not price_match:
                return None
            price = float(price_match.group(1))
            unit = price_match.group(2) or "ea"

            tags = tags_el.get_text(" ", strip=True).lower() if tags_el else ""
            sale_type = "member price" if "member" in tags else "sale"

            return AdItem(
                store=self.store_id,
                item_name=name,
                category="",
                price=price,
                unit=unit,
                sale_type=sale_type,
                valid_from=valid_from,
                valid_to=valid_to,
                scraped_at=scraped_at,
            )
        except (AttributeError, ValueError, TypeError):
            return None

    @staticmethod
    def _parse_valid_to(html: str, modified: str) -> date | None:
        match = _THROUGH_RE.search(html)
        if not match:
            return None
        month_name, day = match.group(1), int(match.group(2))

        ref_date = date.today()
        if modified:
            try:
                ref_date = datetime.fromisoformat(modified).date()
            except ValueError:
                pass

        try:
            candidate = datetime.strptime(
                f"{month_name} {day} {ref_date.year}", "%B %d %Y"
            ).date()
        except ValueError:
            return None

        # Handle sales that roll over the new year (e.g. scraped in late Dec,
        # heading says "Through January 5").
        if candidate.month < ref_date.month - 6:
            candidate = candidate.replace(year=candidate.year + 1)
        return candidate
