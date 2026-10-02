from . import flipp
from .base import BaseConnector
from ..schema import AdItem

# Costco's own site has no weekly ad; Flipp carries its grocery coupon book
# ("CP Grocery") alongside a general-merchandise flyer, and flipp.py picks
# the grocery one. A fair share of the items are still non-food.
MERCHANT_NAME = "Costco"
DEFAULT_LOCATION_ID = "97005"  # Beaverton, OR


class CostcoConnector(BaseConnector):
    store_id = "costco"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> list[AdItem]:
        return flipp.fetch_ad_items(MERCHANT_NAME, self.store_id, self.location_id)
