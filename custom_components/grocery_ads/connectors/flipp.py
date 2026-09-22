"""Shared helper for stores whose weekly ad is served through Flipp's
generic aggregator backend (backflipp.wishabi.com) rather than the store's
own site. Confirmed 2026-09-21 for Albertsons, Safeway, Fred Meyer, and
Grocery Outlet -- fredmeyer.com/kroger.com themselves are unreachable
(connection-level bot-blocking), and while the other three have their own
first-party pages, none of them expose item-level data directly.

Unlike the merchant-scoped Flipp widget APIs some of these same banners
also embed client-side (api.flipp.com/flyerkit, dam.flippenterprise.net --
each needing a per-merchant access token and returning only a flyer PDF
URL), this generic endpoint needs only a postal code, requires no token,
and returns real per-item text (name/price/brand/discount) for whichever
flyer is currently valid -- so these four go through BaseConnector rather
than FlyerConnector. It's a bigger third-party dependency than H Mart's or
Zupan's own site backends: Flipp is an independent aggregator these chains
merely license data to, not first-party infrastructure.
"""
from datetime import date, datetime
import requests
from ..schema import AdItem

FLYERS_URL = "https://backflipp.wishabi.com/flipp/flyers"
FLYER_ITEMS_URL = "https://backflipp.wishabi.com/flipp/flyers/{flyer_id}"


def fetch_ad_items(merchant: str, store_id: str, postal_code: str) -> list[AdItem]:
    flyer = _select_current_flyer(_fetch_flyers(postal_code), merchant)
    if flyer is None:
        return []

    valid_from = _parse_date(flyer.get("valid_from")) or date.today()
    valid_to = _parse_date(flyer.get("valid_to")) or valid_from
    raw_items = _fetch_flyer_items(flyer["id"], postal_code)

    scraped_at = datetime.now()
    items = []
    for raw_item in raw_items:
        item = _parse_item(raw_item, store_id, valid_from, valid_to, scraped_at)
        if item:
            items.append(item)
    return items


def _fetch_flyers(postal_code: str) -> list[dict]:
    resp = requests.get(
        FLYERS_URL,
        params={"locale": "en-us", "postal_code": postal_code},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("flyers", [])


def _fetch_flyer_items(flyer_id: int, postal_code: str) -> list[dict]:
    resp = requests.get(
        FLYER_ITEMS_URL.format(flyer_id=flyer_id),
        params={"locale": "en-us", "postal_code": postal_code},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _select_current_flyer(flyers: list[dict], merchant: str) -> dict | None:
    # Flipp often lists both the actual weekly ad and a longer-running
    # insert/booklet (e.g. Albertsons' "Big Book of Savings") for the same
    # merchant at once; the shortest currently-valid one is the weekly ad.
    today = date.today()
    candidates = []
    for flyer in flyers:
        if flyer.get("merchant", "").strip() != merchant:
            continue
        valid_from = _parse_date(flyer.get("valid_from"))
        valid_to = _parse_date(flyer.get("valid_to"))
        if valid_from is None or valid_to is None:
            continue
        if not (valid_from <= today <= valid_to):
            continue
        candidates.append((valid_to - valid_from, flyer))
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[0])[1]


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_item(
    raw_item: dict,
    store_id: str,
    valid_from: date,
    valid_to: date,
    scraped_at: datetime,
) -> AdItem | None:
    try:
        name = raw_item["name"]
        price = float(raw_item["price"])
        discount = raw_item.get("discount")
        sale_type = f"{discount}% off" if discount else "sale"
        return AdItem(
            store=store_id,
            item_name=name,
            category="",
            price=price,
            unit="",
            sale_type=sale_type,
            valid_from=valid_from,
            valid_to=valid_to,
            scraped_at=scraped_at,
        )
    except (KeyError, TypeError, ValueError):
        return None
