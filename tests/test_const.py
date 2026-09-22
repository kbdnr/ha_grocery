from custom_components.grocery_ads.const import STORE_REGISTRY, STORE_KIND_ITEMS, STORE_KIND_FLYER


def test_registry_has_all_eleven_stores():
    assert set(STORE_REGISTRY) == {
        "hmart",
        "zupans",
        "99ranch",
        "uwajimaya",
        "new_seasons",
        "market_of_choice",
        "asian_family_market",
        "albertsons",
        "safeway",
        "fred_meyer",
        "grocery_outlet",
    }


def test_items_kind_stores():
    for store_id in (
        "hmart",
        "zupans",
        "albertsons",
        "safeway",
        "fred_meyer",
        "grocery_outlet",
    ):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_ITEMS


def test_flyer_stores_are_flyer_kind():
    for store_id in (
        "99ranch",
        "uwajimaya",
        "new_seasons",
        "market_of_choice",
        "asian_family_market",
    ):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_FLYER


def test_only_multi_location_stores_need_location():
    single_location_stores = ("hmart", "zupans", "uwajimaya", "new_seasons", "market_of_choice")
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["needs_location"] == (store_id not in single_location_stores)


def test_registry_key_matches_connector_store_id():
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["connector"].store_id == store_id
