import responses as rsps_lib
from datetime import date
from custom_components.grocery_ads.connectors.asian_family_market import (
    AsianFamilyMarketConnector,
    ENTITY_URL,
    DEFAULT_LOCATION_ID,
)

RECORD = {
    "store": "OR",
    "status": "published",
    "start_date": "2026-09-14",
    "end_date": "2026-10-02",
    "posters": [
        {"display_order": 1, "image_url": "https://media.base44.com/images/b.png"},
        {"display_order": 0, "image_url": "https://media.base44.com/images/a.png"},
    ],
}


@rsps_lib.activate
def test_fetch_returns_flyer_with_posters_sorted_by_display_order():
    rsps_lib.add(rsps_lib.GET, ENTITY_URL, json=[RECORD], status=200)

    flyer = AsianFamilyMarketConnector().fetch()

    assert flyer.store == "asian_family_market"
    assert flyer.media_type == "image"
    assert flyer.urls == [
        "https://media.base44.com/images/a.png",
        "https://media.base44.com/images/b.png",
    ]
    assert flyer.valid_from == date(2026, 9, 14)
    assert flyer.valid_to == date(2026, 10, 2)


@rsps_lib.activate
def test_fetch_returns_none_when_no_records():
    rsps_lib.add(rsps_lib.GET, ENTITY_URL, json=[], status=200)
    assert AsianFamilyMarketConnector().fetch() is None


@rsps_lib.activate
def test_fetch_returns_none_when_record_has_no_posters():
    record = {**RECORD, "posters": []}
    rsps_lib.add(rsps_lib.GET, ENTITY_URL, json=[record], status=200)
    assert AsianFamilyMarketConnector().fetch() is None


@rsps_lib.activate
def test_fetch_falls_back_to_today_when_dates_missing():
    record = {k: v for k, v in RECORD.items() if k not in ("start_date", "end_date")}
    rsps_lib.add(rsps_lib.GET, ENTITY_URL, json=[record], status=200)

    flyer = AsianFamilyMarketConnector().fetch()

    assert flyer.valid_from == date.today()
    assert flyer.valid_to == date.today()


def test_fetch_uses_custom_location_id():
    connector = AsianFamilyMarketConnector(location_id="Bellevue")
    assert connector.location_id == "Bellevue"


def test_default_location_id_is_beaverton_oregon():
    connector = AsianFamilyMarketConnector()
    assert connector.location_id == DEFAULT_LOCATION_ID == "OR"
