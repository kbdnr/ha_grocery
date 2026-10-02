from datetime import date, timedelta
import responses as rsps_lib
from custom_components.grocery_ads.connectors import flipp
from custom_components.grocery_ads.connectors.costco import CostcoConnector, DEFAULT_LOCATION_ID

TODAY = date.today()


def _flyer(flyer_id, name, categories):
    return {
        "id": flyer_id,
        "merchant": "Costco ",  # Flipp's own value has the trailing space
        "name": name,
        "categories_csv": categories,
        "valid_from": (TODAY - timedelta(days=1)).isoformat(),
        "valid_to": (TODAY + timedelta(days=5)).isoformat(),
    }


@rsps_lib.activate
def test_fetch_reads_the_grocery_flyer_not_the_general_merchandise_one():
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYERS_URL,
        json={
            "flyers": [
                _flyer(1, "Flyer", "All Flyers,General Merchandise,Pharmacy,Automotive"),
                _flyer(2, "CP Grocery", "All Flyers,Groceries"),
            ]
        },
        status=200,
    )
    rsps_lib.add(
        rsps_lib.GET,
        flipp.FLYER_ITEMS_URL.format(flyer_id=2),
        json={"items": [{"name": "Kraft Grated Parmesan Cheese, 4.5 lbs", "price": "21.49", "discount": 19}]},
        status=200,
    )

    items = CostcoConnector().fetch()

    assert len(items) == 1
    assert items[0].store == "costco"
    assert items[0].item_name == "Kraft Grated Parmesan Cheese, 4.5 lbs"
    assert items[0].sale_type == "19% off"


def test_fetch_uses_custom_location_id():
    assert CostcoConnector(location_id="90210").location_id == "90210"


def test_default_location_id_is_beaverton_zip():
    assert CostcoConnector().location_id == DEFAULT_LOCATION_ID == "97005"
