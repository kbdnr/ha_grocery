from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.grocery_ads.const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    DOMAIN,
    STORE_KIND_ITEMS,
)
from custom_components.grocery_ads.schema import AdItem
from custom_components.grocery_ads.sensor import async_setup_entry


def make_item():
    return AdItem(
        store="hmart", item_name="Beef", category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_first_items_entry_also_adds_aggregate_sensors(hass):
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {"store_type": "hmart"}

    coordinator = MagicMock()
    coordinator.data = [make_item()]
    aggregate_coordinator = MagicMock()
    aggregate_coordinator.data = {"lowest_price": {}, "diff": {"new": [], "changed": [], "dropped": []}}

    hass.data[DOMAIN] = {
        "entry1": {"coordinator": coordinator},
        AGGREGATE_COORDINATOR_KEY: aggregate_coordinator,
        AGGREGATE_OWNER_KEY: None,
    }

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert len(added) == 3
    assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] == "entry1"


@pytest.mark.asyncio
async def test_second_items_entry_does_not_duplicate_aggregate_sensors(hass):
    entry = MagicMock()
    entry.entry_id = "entry2"
    entry.data = {"store_type": "zupans"}

    coordinator = MagicMock()
    coordinator.data = [make_item()]

    hass.data[DOMAIN] = {
        "entry2": {"coordinator": coordinator},
        AGGREGATE_COORDINATOR_KEY: MagicMock(),
        AGGREGATE_OWNER_KEY: "entry1",
    }

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert len(added) == 1


def test_items_store_with_flyer_exposes_both_in_attributes():
    from custom_components.grocery_ads.schema import FlyerRef
    from custom_components.grocery_ads.sensor import GroceryAdsStoreSensor

    entry = MagicMock()
    entry.entry_id = "entry3"
    entry.data = {"store_type": "uwajimaya"}
    coordinator = MagicMock()
    coordinator.data = [make_item()]
    coordinator.flyer = FlyerRef(
        store="uwajimaya", urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )

    sensor = GroceryAdsStoreSensor(coordinator, entry, STORE_KIND_ITEMS)

    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert attrs["items"] == [make_item().to_dict()]
    assert attrs["urls"] == ["https://example.com/ad.pdf"]
    assert attrs["media_type"] == "pdf"
    assert attrs["flyer_valid_to"] == "2026-09-22"


def test_items_store_keeps_its_flyer_when_there_are_no_items():
    from custom_components.grocery_ads.schema import FlyerRef
    from custom_components.grocery_ads.sensor import GroceryAdsStoreSensor

    entry = MagicMock()
    entry.entry_id = "entry3"
    entry.data = {"store_type": "uwajimaya"}
    coordinator = MagicMock()
    coordinator.data = []
    coordinator.flyer = FlyerRef(
        store="uwajimaya", urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )

    sensor = GroceryAdsStoreSensor(coordinator, entry, STORE_KIND_ITEMS)

    assert sensor.native_value == 0
    assert "items" not in sensor.extra_state_attributes
    assert sensor.extra_state_attributes["urls"] == ["https://example.com/ad.pdf"]


def test_items_store_without_flyer_has_only_items():
    from custom_components.grocery_ads.sensor import GroceryAdsStoreSensor

    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {"store_type": "hmart"}
    coordinator = MagicMock()
    coordinator.data = [make_item()]
    coordinator.flyer = None

    sensor = GroceryAdsStoreSensor(coordinator, entry, STORE_KIND_ITEMS)

    assert sensor.extra_state_attributes == {"items": [make_item().to_dict()]}


def test_flyer_store_state_is_the_flyer_end_date():
    from custom_components.grocery_ads.const import STORE_KIND_FLYER
    from custom_components.grocery_ads.schema import FlyerRef
    from custom_components.grocery_ads.sensor import GroceryAdsStoreSensor

    entry = MagicMock()
    entry.entry_id = "entry2"
    entry.data = {"store_type": "new_seasons"}
    coordinator = MagicMock()
    coordinator.flyer = coordinator.data = FlyerRef(
        store="new_seasons", urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )

    sensor = GroceryAdsStoreSensor(coordinator, entry, STORE_KIND_FLYER)

    assert sensor.native_value == date(2026, 9, 22)
    assert sensor.extra_state_attributes == {"urls": ["https://example.com/ad.pdf"], "media_type": "pdf"}


@pytest.mark.asyncio
async def test_mealie_entry_adds_only_the_recipes_sensor(hass):
    entry = MagicMock()
    entry.entry_id = "mealie_entry"
    entry.data = {"store_type": "mealie"}
    recipe_coordinator = MagicMock()
    recipe_coordinator.data = {
        "count": 40,
        "recipes": [{"name": "Salmon Pasta"}],
        "foods": {"salmon": {"store": "safeway", "item": "Salmon", "price": 9.99}},
        "recipes_indexed": 100,
        "recipes_with_foods": 90,
    }
    hass.data[DOMAIN] = {"mealie_entry": {"recipe_coordinator": recipe_coordinator}}

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert len(added) == 1
    sensor = added[0]
    assert sensor.native_value == 40
    assert sensor.extra_state_attributes["recipes"] == [{"name": "Salmon Pasta"}]
    assert sensor.extra_state_attributes["recipes_indexed"] == 100
    assert "count" not in sensor.extra_state_attributes

    recipe_coordinator.data = None
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}
