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
