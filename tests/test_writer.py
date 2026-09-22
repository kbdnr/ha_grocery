import json
import pytest
from datetime import date, datetime
from pathlib import Path
from custom_components.grocery_ads.schema import AdItem, FlyerRef
from custom_components.grocery_ads.writer import write_latest

def make_item(store, name, price):
    return AdItem(
        store=store, item_name=name, category="Produce", price=price,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


def test_write_latest_creates_json(tmp_path):
    items = [
        make_item("hmart", "Apple", 1.99),
        make_item("hmart", "Banana", 0.49),
        make_item("99ranch", "Apple", 1.79),
    ]
    diff = {"new": [make_item("hmart", "Banana", 0.49)], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path)

    data = json.loads(out_path.read_text())
    assert "hmart" in data
    assert len(data["hmart"]) == 2
    assert "99ranch" in data
    assert "diff" in data
    assert "lowest_price" in data
    assert "scraped_at" in data


def test_lowest_price_computed_correctly(tmp_path):
    items = [
        make_item("hmart", "Apple", 1.99),
        make_item("99ranch", "Apple", 1.79),
    ]
    diff = {"new": [], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path)

    data = json.loads(out_path.read_text())
    assert data["lowest_price"]["Apple"]["price"] == 1.79
    assert data["lowest_price"]["Apple"]["store"] == "99ranch"


def test_write_latest_serializes_changed_diff(tmp_path):
    apple_hmart = make_item("hmart", "Apple", 1.99)
    apple_new = make_item("hmart", "Apple", 1.79)
    diff = {
        "new": [],
        "changed": [{"item": apple_new, "old_price": 1.99}],
        "dropped": [],
    }
    out_path = tmp_path / "latest.json"
    write_latest([apple_hmart], diff, out_path)

    data = json.loads(out_path.read_text())
    assert len(data["diff"]["changed"]) == 1
    changed = data["diff"]["changed"][0]
    assert changed["old_price"] == 1.99
    assert changed["item"]["price"] == 1.79
    assert changed["item"]["item_name"] == "Apple"


def make_flyer(store):
    return FlyerRef(
        store=store, urls=[f"https://example.com/{store}.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


def test_write_latest_includes_flyers(tmp_path):
    items = [make_item("hmart", "Apple", 1.99)]
    diff = {"new": [], "changed": [], "dropped": []}
    flyers = [make_flyer("uwajimaya"), make_flyer("zupans")]
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path, flyers=flyers)

    data = json.loads(out_path.read_text())
    assert "flyers" in data
    assert data["flyers"]["uwajimaya"]["urls"] == ["https://example.com/uwajimaya.pdf"]
    assert data["flyers"]["uwajimaya"]["media_type"] == "pdf"
    assert data["flyers"]["zupans"]["urls"] == ["https://example.com/zupans.pdf"]


def test_write_latest_flyers_defaults_to_empty(tmp_path):
    items = [make_item("hmart", "Apple", 1.99)]
    diff = {"new": [], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path)

    data = json.loads(out_path.read_text())
    assert data["flyers"] == {}


def test_write_latest_rejects_store_id_named_flyers(tmp_path):
    items = [make_item("flyers", "Apple", 1.99)]
    diff = {"new": [], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    with pytest.raises(ValueError, match="flyers"):
        write_latest(items, diff, out_path)
