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


def _flyer_ref():
    from custom_components.grocery_ads.schema import FlyerRef

    return FlyerRef(
        store="uwajimaya", urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_flyer_kind_coordinator_exposes_flyer(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "99ranch"
    connector.fetch.return_value = _flyer_ref()

    coordinator = GroceryAdsCoordinator(hass, connector, STORE_KIND_FLYER, tmp_path / "g.db", "entry2")
    await coordinator.async_refresh()

    assert coordinator.flyer is coordinator.data


@pytest.mark.asyncio
async def test_items_store_with_flyer_connector_gets_both(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "uwajimaya"
    connector.fetch.return_value = [make_item()]
    flyer_connector = MagicMock()
    flyer_connector.fetch.return_value = _flyer_ref()

    coordinator = GroceryAdsCoordinator(
        hass, connector, STORE_KIND_ITEMS, tmp_path / "g.db", "entry3", flyer_connector
    )
    await coordinator.async_refresh()

    assert coordinator.data == [make_item()]
    assert coordinator.flyer == _flyer_ref()


@pytest.mark.asyncio
async def test_items_failure_keeps_the_flyer_and_the_last_items(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "uwajimaya"
    connector.fetch.return_value = [make_item()]
    flyer_connector = MagicMock()
    flyer_connector.fetch.return_value = _flyer_ref()
    coordinator = GroceryAdsCoordinator(
        hass, connector, STORE_KIND_ITEMS, tmp_path / "g.db", "entry3", flyer_connector
    )
    await coordinator.async_refresh()

    connector.fetch.side_effect = RuntimeError("flipp is down")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == [make_item()]
    assert coordinator.flyer == _flyer_ref()


@pytest.mark.asyncio
async def test_flyer_failure_keeps_the_items(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "uwajimaya"
    connector.fetch.return_value = [make_item()]
    flyer_connector = MagicMock()
    flyer_connector.fetch.side_effect = RuntimeError("site is down")

    coordinator = GroceryAdsCoordinator(
        hass, connector, STORE_KIND_ITEMS, tmp_path / "g.db", "entry3", flyer_connector
    )
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == [make_item()]
    assert coordinator.flyer is None


@pytest.mark.asyncio
async def test_both_sources_failing_fails_the_update(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "uwajimaya"
    connector.fetch.side_effect = RuntimeError("flipp is down")
    flyer_connector = MagicMock()
    flyer_connector.fetch.side_effect = RuntimeError("site is down")

    coordinator = GroceryAdsCoordinator(
        hass, connector, STORE_KIND_ITEMS, tmp_path / "g.db", "entry3", flyer_connector
    )
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


def _mealie_client():
    client = MagicMock()
    client.group_slug.return_value = "home"
    client.foods.return_value = [
        {"id": "f-salmon", "name": "salmon", "label": {"name": "Fish"}},
        {"id": "f-butter", "name": "butter", "label": {"name": "Dairy & Eggs"}},
        {"id": "f-pasta", "name": "pasta", "label": {"name": "Pasta"}},
    ]
    client.recipe_summaries.return_value = [
        {"slug": "salmon-pasta", "name": "Salmon Pasta", "updatedAt": "t1"},
        {"slug": "buttered-pasta", "name": "Buttered Pasta", "updatedAt": "t1"},
        {"slug": "unparsed", "name": "Unparsed", "updatedAt": "t1"},
    ]
    client.recipe_food_ids.side_effect = lambda slug: {
        "salmon-pasta": ["f-salmon", "f-butter", "f-pasta"],
        "buttered-pasta": ["f-butter", "f-pasta"],
        "unparsed": [],
    }[slug]
    client.recipe_url.side_effect = lambda group, slug: f"https://mealie.example.com/g/{group}/r/{slug}"
    return client


def _store(items, kind=STORE_KIND_ITEMS):
    store = MagicMock()
    store.kind = kind
    store.data = items
    return {"coordinator": store}


def _ad(store, name, price):
    return AdItem(
        store=store, item_name=name, category="", price=price, unit="", sale_type="sale",
        valid_from=date(2026, 9, 30), valid_to=date(2026, 10, 6),
        scraped_at=datetime(2026, 10, 1, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_recipe_coordinator_ranks_recipes_against_current_store_items(hass, tmp_path):
    from custom_components.grocery_ads.const import DOMAIN
    from custom_components.grocery_ads.coordinator import RecipeCoordinator

    hass.data[DOMAIN] = {
        "safeway_entry": _store([_ad("safeway", "Aqua Star Salmon Fillets", 9.99)]),
        "fm_entry": _store([_ad("fred_meyer", "Coho Salmon Fillets", 7.99), _ad("fred_meyer", "Barilla Pasta", 1.25)]),
        "flyer_entry": _store(MagicMock(), kind=STORE_KIND_FLYER),
        "_aggregate_owner": None,
    }
    coordinator = RecipeCoordinator(hass, _mealie_client(), tmp_path / "recipes.json", None)
    await coordinator.async_refresh()

    data = coordinator.data
    assert coordinator.last_update_success is True
    assert data["count"] == 1
    assert data["recipes_indexed"] == 3
    assert data["recipes_with_foods"] == 2
    recipe = data["recipes"][0]
    assert recipe["name"] == "Salmon Pasta"
    assert recipe["url"] == "https://mealie.example.com/g/home/r/salmon-pasta"
    assert (recipe["on_sale"], recipe["ingredients"]) == (2, 3)
    assert recipe["matches"][0] == {
        "food": "salmon", "store": "fred_meyer", "item": "Coho Salmon Fillets", "price": 7.99,
    }
    assert list(data["foods"]) == ["pasta", "salmon"]
    assert (tmp_path / "recipes.json").exists()


@pytest.mark.asyncio
async def test_recipe_coordinator_recompute_picks_up_new_ads_without_calling_mealie(hass, tmp_path):
    from custom_components.grocery_ads.const import DOMAIN
    from custom_components.grocery_ads.coordinator import RecipeCoordinator

    hass.data[DOMAIN] = {"safeway_entry": _store([])}
    client = _mealie_client()
    coordinator = RecipeCoordinator(hass, client, tmp_path / "recipes.json", None)

    coordinator.async_recompute()  # before the first sync: nothing to match against yet
    assert coordinator.data is None

    await coordinator.async_refresh()
    assert coordinator.data["count"] == 0
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    calls_before = client.recipe_summaries.call_count

    hass.data[DOMAIN]["safeway_entry"] = _store([_ad("safeway", "Challenge Butter", 3.99)])
    coordinator.async_recompute()

    assert coordinator.data["count"] == 2
    assert client.recipe_summaries.call_count == calls_before
    listener.assert_called_once()
    await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_recipe_coordinator_second_sync_only_refetches_changed_recipes(hass, tmp_path):
    from custom_components.grocery_ads.const import DOMAIN
    from custom_components.grocery_ads.coordinator import RecipeCoordinator

    hass.data[DOMAIN] = {}
    client = _mealie_client()
    coordinator = RecipeCoordinator(hass, client, tmp_path / "recipes.json", None)
    await coordinator.async_refresh()
    assert client.recipe_food_ids.call_count == 3

    client.recipe_summaries.return_value[0]["updatedAt"] = "t2"
    await coordinator.async_refresh()

    assert client.recipe_food_ids.call_count == 4


@pytest.mark.asyncio
async def test_recipe_coordinator_reports_failure_when_mealie_is_unreachable(hass, tmp_path):
    from custom_components.grocery_ads.const import DOMAIN
    from custom_components.grocery_ads.coordinator import RecipeCoordinator

    hass.data[DOMAIN] = {}
    client = _mealie_client()
    client.group_slug.side_effect = RuntimeError("connection refused")
    coordinator = RecipeCoordinator(hass, client, tmp_path / "recipes.json", None)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
