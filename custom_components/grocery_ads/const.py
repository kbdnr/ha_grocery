from .connectors.albertsons import AlbertsonsConnector
from .connectors.asian_family_market import AsianFamilyMarketConnector
from .connectors.fred_meyer import FredMeyerConnector
from .connectors.grocery_outlet import GroceryOutletConnector
from .connectors.hmart import HMartConnector
from .connectors.market_of_choice import MarketOfChoiceConnector
from .connectors.new_seasons import NewSeasonsConnector
from .connectors.ranch99 import Ranch99Connector
from .connectors.safeway import SafewayConnector
from .connectors.uwajimaya import UwajimayaConnector
from .connectors.zupans import ZupansConnector

DOMAIN = "grocery_ads"
DB_FILENAME = "groceries.db"

CONF_STORE_TYPE = "store_type"
CONF_LOCATION_ID = "location_id"

STORE_KIND_ITEMS = "items"
STORE_KIND_FLYER = "flyer"

STORE_REGISTRY = {
    "hmart": {
        "name": "H Mart",
        "connector": HMartConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": False,
    },
    "zupans": {
        "name": "Zupan's Markets",
        "connector": ZupansConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": False,
    },
    "99ranch": {
        "name": "99 Ranch Market",
        "connector": Ranch99Connector,
        "kind": STORE_KIND_FLYER,
        "needs_location": True,
    },
    "uwajimaya": {
        "name": "Uwajimaya",
        "connector": UwajimayaConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": False,
    },
    "new_seasons": {
        "name": "New Seasons Market",
        "connector": NewSeasonsConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": False,
    },
    "market_of_choice": {
        "name": "Market of Choice",
        "connector": MarketOfChoiceConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": False,
    },
    "asian_family_market": {
        "name": "Asian Family Market",
        "connector": AsianFamilyMarketConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": True,
    },
    "albertsons": {
        "name": "Albertsons",
        "connector": AlbertsonsConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
    },
    "safeway": {
        "name": "Safeway",
        "connector": SafewayConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
    },
    "fred_meyer": {
        "name": "Fred Meyer",
        "connector": FredMeyerConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
    },
    "grocery_outlet": {
        "name": "Grocery Outlet",
        "connector": GroceryOutletConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
    },
}

AGGREGATE_COORDINATOR_KEY = "_aggregate_coordinator"
AGGREGATE_OWNER_KEY = "_aggregate_owner"
