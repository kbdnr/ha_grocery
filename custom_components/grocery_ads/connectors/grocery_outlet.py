from . import flipp
from .base import BaseConnector
from ..schema import AdItem

MERCHANT_NAME = "Grocery Outlet"
DEFAULT_LOCATION_ID = "97005"  # Beaverton, OR


class GroceryOutletConnector(BaseConnector):
    store_id = "grocery_outlet"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> list[AdItem]:
        return flipp.fetch_ad_items(MERCHANT_NAME, self.store_id, self.location_id)
