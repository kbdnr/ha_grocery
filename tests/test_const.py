from custom_components.grocery_ads.const import (
    LOCATION_POSTAL_CODE,
    LOCATION_STORE,
    STORE_REGISTRY,
    STORE_KIND_ITEMS,
    STORE_KIND_FLYER,
)


def test_registry_has_all_twelve_stores():
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
        "costco",
    }


def test_items_kind_stores():
    for store_id in (
        "hmart",
        "zupans",
        "albertsons",
        "safeway",
        "fred_meyer",
        "grocery_outlet",
        "costco",
        "uwajimaya",
    ):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_ITEMS


def test_flyer_stores_are_flyer_kind():
    for store_id in (
        "99ranch",
        "new_seasons",
        "market_of_choice",
        "asian_family_market",
    ):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_FLYER


def test_uwajimaya_is_the_only_items_store_that_also_has_a_flyer():
    with_flyer = [store_id for store_id, conf in STORE_REGISTRY.items() if "flyer_connector" in conf]
    assert with_flyer == ["uwajimaya"]
    assert STORE_REGISTRY["uwajimaya"]["flyer_connector"].store_id == "uwajimaya"


def test_only_multi_location_stores_need_location():
    single_location_stores = ("hmart", "zupans", "uwajimaya", "new_seasons", "market_of_choice")
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["needs_location"] == (store_id not in single_location_stores)


def test_location_stores_say_how_the_location_is_asked_for():
    for store_id, conf in STORE_REGISTRY.items():
        if not conf["needs_location"]:
            assert "location_kind" not in conf
        elif store_id in ("99ranch", "asian_family_market"):
            assert conf["location_kind"] == LOCATION_STORE
            assert callable(conf["connector"].list_locations)
        else:
            assert conf["location_kind"] == LOCATION_POSTAL_CODE


def test_registry_key_matches_connector_store_id():
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["connector"].store_id == store_id
