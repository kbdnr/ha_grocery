from .connectors.albertsons import AlbertsonsConnector
from .connectors.asian_family_market import AsianFamilyMarketConnector
from .connectors.costco import CostcoConnector
from .connectors.fred_meyer import FredMeyerConnector
from .connectors.grocery_outlet import GroceryOutletConnector
from .connectors.hmart import HMartConnector
from .connectors.market_of_choice import MarketOfChoiceConnector
from .connectors.new_seasons import NewSeasonsConnector
from .connectors.ranch99 import Ranch99Connector
from .connectors.safeway import SafewayConnector
from .connectors.uwajimaya import UwajimayaConnector, UwajimayaItemsConnector
from .connectors.zupans import ZupansConnector

DOMAIN = "grocery_ads"
DB_FILENAME = "groceries.db"

CONF_STORE_TYPE = "store_type"
CONF_LOCATION_ID = "location_id"
CONF_URL = "url"
CONF_TOKEN = "token"

# Not a store: the config entry that connects a Mealie instance, picked from
# the same dropdown as the stores and stored under the same CONF_STORE_TYPE.
ENTRY_TYPE_MEALIE = "mealie"
MEALIE_ENTRY_NAME = "Mealie (recipes on sale)"
RECIPE_CACHE_FILENAME = "mealie_recipes.json"

STORE_KIND_ITEMS = "items"
STORE_KIND_FLYER = "flyer"

# What a needs_location store's CONF_LOCATION_ID holds, which decides how the
# config flow asks for it: a ZIP code typed in (the Flipp stores), or one of
# the connector's list_locations() picked from a dropdown.
LOCATION_POSTAL_CODE = "postal_code"
LOCATION_STORE = "store"

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
        "location_kind": LOCATION_STORE,
    },
    # Items (via Flipp) and the PDF flyer (from the store's own site): an
    # items store whose coordinator also runs a second, flyer connector.
    "uwajimaya": {
        "name": "Uwajimaya",
        "connector": UwajimayaItemsConnector,
        "flyer_connector": UwajimayaConnector,
        "kind": STORE_KIND_ITEMS,
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
        "location_kind": LOCATION_STORE,
    },
    "albertsons": {
        "name": "Albertsons",
        "connector": AlbertsonsConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
        "location_kind": LOCATION_POSTAL_CODE,
    },
    "safeway": {
        "name": "Safeway",
        "connector": SafewayConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
        "location_kind": LOCATION_POSTAL_CODE,
    },
    "fred_meyer": {
        "name": "Fred Meyer",
        "connector": FredMeyerConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
        "location_kind": LOCATION_POSTAL_CODE,
    },
    "grocery_outlet": {
        "name": "Grocery Outlet",
        "connector": GroceryOutletConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
        "location_kind": LOCATION_POSTAL_CODE,
    },
    "costco": {
        "name": "Costco",
        "connector": CostcoConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": True,
        "location_kind": LOCATION_POSTAL_CODE,
    },
}

AGGREGATE_COORDINATOR_KEY = "_aggregate_coordinator"
AGGREGATE_OWNER_KEY = "_aggregate_owner"
RECIPE_COORDINATOR_KEY = "_recipe_coordinator"
