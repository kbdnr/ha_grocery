from datetime import date, timedelta
import responses as rsps_lib
from custom_components.grocery_ads.connectors import flipp
from custom_components.grocery_ads.connectors.grocery_outlet import GroceryOutletConnector, DEFAULT_LOCATION_ID

TODAY = date.today()


@rsps_lib.activate
def test_fetch_returns_ad_items_for_grocery_outlet_merchant():
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYERS_URL,
        json={
            "flyers": [
                {
                    "id": 1,
                    "merchant": "Grocery Outlet",
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
        json={"items": [{"name": "Klondike Cones", "price": "4.99", "discount": 55}]},
        status=200,
    )

    items = GroceryOutletConnector().fetch()

    assert len(items) == 1
    assert items[0].store == "grocery_outlet"
    assert items[0].item_name == "Klondike Cones"
    assert items[0].sale_type == "55% off"


def test_fetch_uses_custom_location_id():
    connector = GroceryOutletConnector(location_id="90210")
    assert connector.location_id == "90210"


def test_default_location_id_is_beaverton_zip():
    assert GroceryOutletConnector().location_id == DEFAULT_LOCATION_ID == "97005"
