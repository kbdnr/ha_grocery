from datetime import date, datetime
from custom_components.grocery_ads.schema import AdItem, FlyerRef


def test_aditem_creation():
    item = AdItem(
        store="hmart",
        item_name="Wagyu Beef",
        category="Meat",
        price=12.99,
        unit="lb",
        sale_type="sale",
        valid_from=date(2026, 8, 28),
        valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    assert item.store == "hmart"
    assert item.price == 12.99
    assert item.item_name == "Wagyu Beef"
    assert item.category == "Meat"
    assert item.unit == "lb"
    assert item.sale_type == "sale"
    assert item.valid_from == date(2026, 8, 28)
    assert item.valid_to == date(2026, 9, 3)
    assert item.scraped_at == datetime(2026, 8, 29, 6, 0, 0)


def test_aditem_to_dict():
    item = AdItem(
        store="hmart",
        item_name="Wagyu Beef",
        category="Meat",
        price=12.99,
        unit="lb",
        sale_type="sale",
        valid_from=date(2026, 8, 28),
        valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    d = item.to_dict()
    assert d["store"] == "hmart"
    assert d["price"] == 12.99
    assert d["valid_from"] == "2026-08-28"
    assert d["valid_to"] == "2026-09-03"
    assert d["scraped_at"] == "2026-08-29T06:00:00"
    assert set(d.keys()) == {
        "store", "item_name", "category", "price", "unit",
        "sale_type", "valid_from", "valid_to", "scraped_at",
    }


def test_aditem_coerces_price_from_string():
    item = AdItem(
        store="hmart", item_name="Apple", category="Produce",
        price="1.99",  # string — should be coerced to float
        unit="lb", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    assert item.price == 1.99
    assert isinstance(item.price, float)


def test_flyerref_creation_and_to_dict():
    flyer = FlyerRef(
        store="uwajimaya",
        urls=["https://www.uwajimaya.com/wp-content/uploads/2026/09/WeeklyAd.pdf"],
        media_type="pdf",
        valid_from=date(2026, 9, 16),
        valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )
    d = flyer.to_dict()
    assert d == {
        "store": "uwajimaya",
        "urls": ["https://www.uwajimaya.com/wp-content/uploads/2026/09/WeeklyAd.pdf"],
        "media_type": "pdf",
        "valid_from": "2026-09-16",
        "valid_to": "2026-09-22",
        "scraped_at": "2026-09-21T06:00:00",
    }


def test_flyerref_supports_multiple_urls():
    flyer = FlyerRef(
        store="99ranch",
        urls=["https://img.example.com/a.jpeg", "https://img.example.com/b.jpeg"],
        media_type="image",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )
    assert len(flyer.urls) == 2


def test_flyerref_coerces_string_dates():
    flyer = FlyerRef(
        store="zupans", urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from="2026-09-16", valid_to="2026-09-22",
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )
    assert flyer.valid_from == date(2026, 9, 16)
    assert flyer.valid_to == date(2026, 9, 22)
