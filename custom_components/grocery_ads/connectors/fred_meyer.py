from . import flipp
from .base import BaseConnector
from ..schema import AdItem

# fredmeyer.com/kroger.com are unreachable to non-browser clients (Akamai-
# style connection-level bot-blocking, confirmed 2026-09-21) -- Fred Meyer's
# weekly ad is only readable through Flipp's generic aggregator backend, not
# the store's own site.
MERCHANT_NAME = "Fred Meyer"
DEFAULT_LOCATION_ID = "97005"  # Beaverton, OR


class FredMeyerConnector(BaseConnector):
    store_id = "fred_meyer"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> list[AdItem]:
        return flipp.fetch_ad_items(MERCHANT_NAME, self.store_id, self.location_id)
