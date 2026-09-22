from datetime import date, datetime, timedelta
import pytest
import responses as rsps_lib
from custom_components.grocery_ads.connectors import flipp

POSTAL_CODE = "97005"
TODAY = date.today()


def _iso(d: date) -> str:
    return datetime.combine(d, datetime.min.time()).isoformat()


def _flyer(flyer_id, merchant, valid_from, valid_to):
    return {
        "id": flyer_id,
        "merchant": merchant,
        "name": "Weekly Ad",
        "valid_from": _iso(valid_from),
        "valid_to": _iso(valid_to),
    }


@rsps_lib.activate
def test_fetch_ad_items_picks_shortest_currently_valid_flyer_for_merchant():
    flyers = [
        _flyer(1, "Albertsons", TODAY - timedelta(days=30), TODAY + timedelta(days=30)),  # long-running insert
        _flyer(2, "Albertsons", TODAY - timedelta(days=2), TODAY + timedelta(days=4)),  # actual weekly ad
        _flyer(3, "Safeway", TODAY - timedelta(days=2), TODAY + timedelta(days=4)),  # other merchant
        _flyer(4, "Albertsons", TODAY + timedelta(days=10), TODAY + timedelta(days=17)),  # not yet valid
    ]
    rsps_lib.add(
        rsps_lib.GET, flipp.FLYERS_URL, json={"flyers": flyers}, status=200,
    )
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYER_ITEMS_URL.format(flyer_id=2),
        json={
            "items": [
                {"name": "Fresh Whole Chicken", "price": "0.99", "brand": "Signature SELECT", "discount": None},
                {"name": "Broccoli Crowns", "price": "1.49", "brand": None, "discount": 40},
            ]
        },
        status=200,
    )

    items = flipp.fetch_ad_items("Albertsons", "albertsons", POSTAL_CODE)

    assert len(items) == 2
    chicken, broccoli = items
    assert chicken.store == "albertsons"
    assert chicken.item_name == "Fresh Whole Chicken"
    assert chicken.price == 0.99
    assert chicken.sale_type == "sale"
    assert chicken.valid_from == TODAY - timedelta(days=2)
    assert chicken.valid_to == TODAY + timedelta(days=4)
    assert broccoli.sale_type == "40% off"


@rsps_lib.activate
def test_fetch_ad_items_returns_empty_when_no_current_flyer_for_merchant():
    rsps_lib.add(rsps_lib.GET, flipp.FLYERS_URL, json={"flyers": []}, status=200)
    assert flipp.fetch_ad_items("Fred Meyer", "fred_meyer", POSTAL_CODE) == []


@rsps_lib.activate
def test_fetch_ad_items_skips_items_missing_required_fields():
    flyers = [_flyer(5, "Grocery Outlet", TODAY, TODAY + timedelta(days=6))]
    rsps_lib.add(rsps_lib.GET, flipp.FLYERS_URL, json={"flyers": flyers}, status=200)
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYER_ITEMS_URL.format(flyer_id=5),
        json={"items": [{"name": "No Price Item"}, {"name": "Klondike Cones", "price": "4.99"}]},
        status=200,
    )

    items = flipp.fetch_ad_items("Grocery Outlet", "grocery_outlet", POSTAL_CODE)

    assert len(items) == 1
    assert items[0].item_name == "Klondike Cones"
