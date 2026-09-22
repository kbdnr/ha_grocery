import argparse
import sys
from pathlib import Path
from custom_components.grocery_ads.connectors.hmart import HMartConnector
from custom_components.grocery_ads.connectors.ranch99 import Ranch99Connector
from custom_components.grocery_ads.connectors.uwajimaya import UwajimayaConnector
from custom_components.grocery_ads.connectors.zupans import ZupansConnector
from custom_components.grocery_ads.connectors.new_seasons import NewSeasonsConnector
from custom_components.grocery_ads.db import Database
from custom_components.grocery_ads.writer import write_latest

CONNECTORS = [
    HMartConnector(),
    ZupansConnector(),
]

FLYER_CONNECTORS = [
    Ranch99Connector(),
    UwajimayaConnector(),
    NewSeasonsConnector(),
]

DB_PATH = Path("groceries.db")
JSON_PATH = Path("latest.json")


def run(db_path: Path = DB_PATH, json_path: Path = JSON_PATH, stores: list[str] | None = None, dry_run: bool = False) -> int:
    db = Database(db_path)
    all_items = []
    flyers = []
    failed = 0
    attempted = 0

    for connector in CONNECTORS:
        if stores and connector.store_id not in stores:
            continue
        attempted += 1
        try:
            items = connector.fetch()
            print(f"[{connector.store_id}] fetched {len(items)} items")
            all_items.extend(items)
        except Exception as e:
            print(f"[{connector.store_id}] ERROR: {e}", file=sys.stderr)
            failed += 1

    for connector in FLYER_CONNECTORS:
        if stores and connector.store_id not in stores:
            continue
        attempted += 1
        try:
            flyer = connector.fetch()
            if flyer:
                print(f"[{connector.store_id}] fetched flyer ({flyer.media_type})")
                flyers.append(flyer)
            else:
                print(f"[{connector.store_id}] no flyer found")
        except Exception as e:
            print(f"[{connector.store_id}] ERROR: {e}", file=sys.stderr)
            failed += 1

    if attempted > 0 and failed == attempted:
        print("No items fetched — all connectors failed.", file=sys.stderr)
        return 1

    if not dry_run:
        if all_items:
            db.insert_items(all_items)
        diff = db.compute_diff()
        write_latest(db.get_latest_items(), diff, json_path, flyers=flyers)
        print(f"Wrote {json_path}")
    else:
        for item in all_items:
            print(item)
        for flyer in flyers:
            print(flyer)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", help="Comma-separated store IDs to run")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stores = args.stores.split(",") if args.stores else None
    sys.exit(run(stores=stores, dry_run=args.dry_run))
