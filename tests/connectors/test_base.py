import pytest
from datetime import date, datetime
from custom_components.grocery_ads.connectors.base import BaseConnector, FlyerConnector
from custom_components.grocery_ads.schema import FlyerRef


def test_cannot_instantiate_without_fetch():
    class BadConnector(BaseConnector):
        store_id = "bad"

    with pytest.raises(TypeError):
        BadConnector()


def test_can_instantiate_with_fetch():
    class GoodConnector(BaseConnector):
        store_id = "good"

        def fetch(self):
            return []

    connector = GoodConnector()
    assert connector.fetch() == []


def test_concrete_connector_without_store_id_raises():
    with pytest.raises(TypeError, match="store_id"):
        class NoStoreId(BaseConnector):
            def fetch(self):
                return []


def test_abstract_subclass_without_store_id_is_fine():
    # Abstract intermediaries (still have abstractmethods) don't need store_id yet
    class AbstractMiddle(BaseConnector):
        pass  # still abstract — no fetch()
    # Should not raise at class definition time
    # (instantiation would still raise TypeError from ABC)
    with pytest.raises(TypeError):
        AbstractMiddle()


def make_flyer(store="uwajimaya"):
    return FlyerRef(
        store=store, urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


def test_flyer_connector_cannot_instantiate_without_fetch():
    class BadFlyerConnector(FlyerConnector):
        store_id = "bad"

    with pytest.raises(TypeError):
        BadFlyerConnector()


def test_flyer_connector_can_instantiate_with_fetch():
    class GoodFlyerConnector(FlyerConnector):
        store_id = "good"

        def fetch(self):
            return make_flyer("good")

    connector = GoodFlyerConnector()
    flyer = connector.fetch()
    assert flyer.store == "good"


def test_flyer_connector_concrete_without_store_id_raises():
    with pytest.raises(TypeError, match="store_id"):
        class NoStoreIdFlyer(FlyerConnector):
            def fetch(self):
                return None
