import json
from datetime import datetime
from pathlib import Path
from .schema import AdItem, FlyerRef

_RESERVED = {"diff", "lowest_price", "scraped_at", "flyers"}


def write_latest(
    items: list[AdItem],
    diff: dict,
    path: str | Path,
    flyers: list[FlyerRef] | None = None,
) -> None:
    by_store: dict[str, list] = {}
    for item in items:
        by_store.setdefault(item.store, []).append(item.to_dict())

    reserved_collision = set(by_store.keys()) & _RESERVED
    if reserved_collision:
        raise ValueError(f"Store ID(s) collide with reserved JSON keys: {reserved_collision}")

    lowest: dict[str, dict] = {}
    for item in items:
        if item.item_name not in lowest or item.price < lowest[item.item_name]["price"]:
            lowest[item.item_name] = {"store": item.store, "price": item.price}

    diff_out = {
        "new": [i.to_dict() for i in diff.get("new", [])],
        "changed": [
            {"item": c["item"].to_dict(), "old_price": c["old_price"]}
            for c in diff.get("changed", [])
        ],
        "dropped": [i.to_dict() for i in diff.get("dropped", [])],
    }

    output = {
        **by_store,
        "diff": diff_out,
        "lowest_price": lowest,
        "flyers": {f.store: f.to_dict() for f in (flyers or [])},
        "scraped_at": datetime.now().isoformat(),
    }

    Path(path).write_text(json.dumps(output, indent=2))
