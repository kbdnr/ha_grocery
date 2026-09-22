from .connectors.hmart import HMartConnector
from .connectors.new_seasons import NewSeasonsConnector
from .connectors.ranch99 import Ranch99Connector
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
}

AGGREGATE_COORDINATOR_KEY = "_aggregate_coordinator"
AGGREGATE_OWNER_KEY = "_aggregate_owner"
