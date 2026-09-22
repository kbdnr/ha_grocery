import pytest
from datetime import date, datetime
from custom_components.grocery_ads.db import Database
from custom_components.grocery_ads.schema import AdItem


def make_item(store="hmart", name="Beef", price=10.0, valid_from=None, valid_to=None):
    return AdItem(
        store=store,
        item_name=name,
        category="Meat",
        price=price,
        unit="lb",
        sale_type="sale",
        valid_from=valid_from or date(2026, 8, 28),
        valid_to=valid_to or date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_insert_and_get_latest(db):
    items = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    db.insert_items(items)
    latest = db.get_latest_items()
    assert len(latest) == 2


def test_get_latest_returns_only_most_recent_scrape(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 9.0)]
    db.insert_items(old)
    db.insert_items(new)
    latest = db.get_latest_items()
    assert len(latest) == 1
    assert latest[0].price == 9.0


def test_diff_finds_new_items(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["new"]) == 1
    assert diff["new"][0].item_name == "Pork"


def test_diff_finds_price_changes(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 9.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["item"].price == 9.0
    assert diff["changed"][0]["old_price"] == 10.0


def test_diff_finds_dropped_items(db):
    old = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    new = [make_item("hmart", "Beef", 10.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["dropped"]) == 1
    assert diff["dropped"][0].item_name == "Pork"


def test_diff_handles_same_name_different_unit(db):
    old = [make_item("hmart", "Beef", 10.0)]  # unit="lb" from make_item
    # Add a new item: same name, different unit
    pkg_beef = AdItem(
        store="hmart", item_name="Beef", category="Meat",
        price=25.0, unit="pkg", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    new = [make_item("hmart", "Beef", 10.0), pkg_beef]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    # pkg_beef is new (different unit), lb Beef is unchanged
    assert len(diff["new"]) == 1
    assert diff["new"][0].unit == "pkg"
    assert len(diff["changed"]) == 0
