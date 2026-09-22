from datetime import date, timedelta
import responses as rsps_lib
from custom_components.grocery_ads.connectors import flipp
from custom_components.grocery_ads.connectors.fred_meyer import FredMeyerConnector, DEFAULT_LOCATION_ID

TODAY = date.today()


@rsps_lib.activate
def test_fetch_returns_ad_items_for_fred_meyer_merchant():
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYERS_URL,
        json={
            "flyers": [
                {
                    "id": 1,
                    "merchant": "Fred Meyer",
                    "valid_from": (TODAY - timedelta(days=1)).isoformat(),
                    "valid_to": (TODAY + timedelta(days=5)).isoformat(),
                },
                {
                    "id": 2,
                    "merchant": "QFC",
                    "valid_from": (TODAY - timedelta(days=1)).isoformat(),
                    "valid_to": (TODAY + timedelta(days=5)).isoformat(),
                },
            ]
        },
        status=200,
    )
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYER_ITEMS_URL.format(flyer_id=1),
        json={"items": [{"name": "Waterfront Bistro Cioppino Sauce", "price": "3.99"}]},
        status=200,
    )

    items = FredMeyerConnector().fetch()

    assert len(items) == 1
    assert items[0].store == "fred_meyer"
    assert items[0].item_name == "Waterfront Bistro Cioppino Sauce"


def test_fetch_uses_custom_location_id():
    connector = FredMeyerConnector(location_id="90210")
    assert connector.location_id == "90210"


def test_default_location_id_is_beaverton_zip():
    assert FredMeyerConnector().location_id == DEFAULT_LOCATION_ID == "97005"
