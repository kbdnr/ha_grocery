import pytest
import responses as rsps_lib
from custom_components.grocery_ads.connectors.hmart import HMartConnector

MOCK_VTEX_RESPONSE = [
    {
        "productName": "Wagyu Beef Sliced",
        "categories": ["/Meat/Beef/"],
        "items": [
            {
                "measurementUnit": "un",
                "sellers": [
                    {
                        "commertialOffer": {
                            "Price": 12.99,
                            "ListPrice": 15.99,
                            "PriceValidUntil": "2026-09-10T23:59:59",
                        }
                    }
                ],
            }
        ],
    }
]


@rsps_lib.activate
def test_fetch_returns_ad_items():
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=MOCK_VTEX_RESPONSE,
        headers={"resources": "0-0/1"},
        status=200,
    )

    connector = HMartConnector()
    items = connector.fetch()

    assert len(items) == 1
    item = items[0]
    assert item.store == "hmart"
    assert item.item_name == "Wagyu Beef Sliced"
    assert item.price == 12.99
    assert item.sale_type == "sale"
    assert item.unit == "un"
    assert item.category == "Beef"


@rsps_lib.activate
def test_fetch_paginates_correctly():
    # First page: 1 item, total=2 (so there's a page 2)
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=MOCK_VTEX_RESPONSE,
        headers={"resources": "0-0/2"},
        status=200,
    )
    # Second page: 1 item, total=2 (offset 1 now covers all)
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=MOCK_VTEX_RESPONSE,
        headers={"resources": "1-1/2"},
        status=200,
    )

    connector = HMartConnector()
    items = connector.fetch()
    assert len(items) == 2


@rsps_lib.activate
def test_fetch_handles_empty_response():
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=[],
        headers={"resources": "0-0/0"},
        status=200,
    )
    connector = HMartConnector()
    assert connector.fetch() == []


@rsps_lib.activate
def test_fetch_skips_malformed_items():
    malformed = {
        "productName": "Bad Item",
        "categories": ["/Meat/"],
        "items": [
            {
                "measurementUnit": "un",
                "sellers": [
                    {
                        "commertialOffer": {
                            "Price": None,  # null price — should be skipped
                            "ListPrice": None,
                            "PriceValidUntil": "2026-09-10T23:59:59",
                        }
                    }
                ],
            }
        ],
    }
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=[malformed],
        headers={"resources": "0-0/1"},
        status=200,
    )
    connector = HMartConnector()
    items = connector.fetch()
    assert items == []
