from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.grocery_ads.const import STORE_KIND_FLYER, STORE_KIND_ITEMS
from custom_components.grocery_ads.coordinator import AggregateCoordinator, GroceryAdsCoordinator
from custom_components.grocery_ads.schema import AdItem


def make_item():
    return AdItem(
        store="hmart", item_name="Beef", category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_items_kind_coordinator_persists_to_db(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "hmart"
    connector.fetch.return_value = [make_item()]
    db_path = tmp_path / "groceries.db"

    coordinator = GroceryAdsCoordinator(hass, connector, STORE_KIND_ITEMS, db_path, "entry1")
    await coordinator.async_refresh()

    assert coordinator.data == [make_item()]

    from custom_components.grocery_ads.db import Database
    db = Database(db_path)
    assert len(db.get_latest_items()) == 1


@pytest.mark.asyncio
async def test_flyer_kind_coordinator_does_not_touch_db(hass, tmp_path):
    from custom_components.grocery_ads.schema import FlyerRef

    connector = MagicMock()
    connector.store_id = "99ranch"
    flyer = FlyerRef(
        store="99ranch", urls=["https://example.com/a.jpg"], media_type="image",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )
    connector.fetch.return_value = flyer
    db_path = tmp_path / "groceries.db"

    coordinator = GroceryAdsCoordinator(hass, connector, STORE_KIND_FLYER, db_path, "entry2")
    await coordinator.async_refresh()

    assert coordinator.data == flyer
    assert not db_path.exists()


@pytest.mark.asyncio
async def test_aggregate_coordinator_reads_diff_and_lowest_price(hass, tmp_path):
    db_path = tmp_path / "groceries.db"
    from custom_components.grocery_ads.db import Database
    db = Database(db_path)
    db.insert_items([make_item()])

    coordinator = AggregateCoordinator(hass, db_path)
    await coordinator.async_refresh()

    assert coordinator.data["lowest_price"] == {"Beef": {"store": "hmart", "price": 10.0}}
    assert coordinator.data["diff"]["new"] == [make_item()]
