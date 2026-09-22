from datetime import date, datetime
import requests
from .base import BaseConnector
from ..schema import AdItem

WEEKLY_SALE_CLUSTER_ID = 208
BASE_URL = "https://www.hmart.com/api/catalog_system/pub/products/search"
PAGE_SIZE = 49


class HMartConnector(BaseConnector):
    store_id = "hmart"

    def fetch(self) -> list[AdItem]:
        items = []
        offset = 0
        total = None

        while True:
            resp = requests.get(
                BASE_URL,
                params={
                    "fq": f"productClusterIds:{WEEKLY_SALE_CLUSTER_ID}",
                    "_from": offset,
                    "_to": offset + PAGE_SIZE - 1,
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()

            if total is None:
                resources = resp.headers.get("resources", "0-0/0")
                total = int(resources.split("/")[-1])
                if total == 0:
                    break

            page = resp.json()
            for product in page:
                item = self._parse_product(product)
                if item:
                    items.append(item)

            offset += len(page) if page else PAGE_SIZE
            if not page or offset >= total:
                break

        return items

    def _parse_product(self, product: dict) -> AdItem | None:
        try:
            name = product["productName"]

            categories = product.get("categories", [])
            category = ""
            if categories:
                parts = [p for p in categories[0].split("/") if p.strip()]
                category = parts[-1] if parts else ""

            item_data = product.get("items", [{}])[0]
            unit = item_data.get("measurementUnit", "un")
            seller = item_data.get("sellers", [{}])[0]
            offer = seller.get("commertialOffer", {})
            price = float(offer.get("Price", 0))
            list_price = float(offer.get("ListPrice", price))
            sale_type = "sale" if price < list_price else "regular"

            price_valid_until = offer.get("PriceValidUntil", "")
            valid_to = (
                datetime.fromisoformat(price_valid_until).date()
                if price_valid_until
                else date.today()
            )
            valid_from = date.today()

            return AdItem(
                store=self.store_id,
                item_name=name,
                category=category,
                price=price,
                unit=unit,
                sale_type=sale_type,
                valid_from=valid_from,
                valid_to=valid_to,
                scraped_at=datetime.now(),
            )
        except (KeyError, IndexError, ValueError, TypeError, AttributeError):
            return None
