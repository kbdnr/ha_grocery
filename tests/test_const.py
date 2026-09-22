from custom_components.grocery_ads.const import STORE_REGISTRY, STORE_KIND_ITEMS, STORE_KIND_FLYER


def test_registry_has_all_five_stores():
    assert set(STORE_REGISTRY) == {"hmart", "zupans", "99ranch", "uwajimaya", "new_seasons"}


def test_hmart_and_zupans_are_items_kind():
    assert STORE_REGISTRY["hmart"]["kind"] == STORE_KIND_ITEMS
    assert STORE_REGISTRY["zupans"]["kind"] == STORE_KIND_ITEMS


def test_flyer_stores_are_flyer_kind():
    for store_id in ("99ranch", "uwajimaya", "new_seasons"):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_FLYER


def test_only_99ranch_needs_location():
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["needs_location"] == (store_id == "99ranch")


def test_registry_key_matches_connector_store_id():
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["connector"].store_id == store_id
