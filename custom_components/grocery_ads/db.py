import sqlite3
from datetime import date, datetime
from pathlib import Path
from .schema import AdItem

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS ad_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_batch TEXT NOT NULL,
    store TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    price REAL NOT NULL,
    unit TEXT NOT NULL,
    sale_type TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,
    scraped_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scrape_batch ON ad_items(scrape_batch);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def insert_items(self, items: list[AdItem]) -> None:
        batch = datetime.now().isoformat()
        rows = [
            (
                batch,
                item.store,
                item.item_name,
                item.category,
                item.price,
                item.unit,
                item.sale_type,
                item.valid_from.isoformat(),
                item.valid_to.isoformat(),
                item.scraped_at.isoformat(),
            )
            for item in items
        ]
        self._conn.executemany(
            "INSERT INTO ad_items (scrape_batch, store, item_name, category, price, unit, sale_type, valid_from, valid_to, scraped_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self._conn.commit()

    def _parse_row(self, row) -> AdItem:
        _, _, store, item_name, category, price, unit, sale_type, valid_from, valid_to, scraped_at = row
        return AdItem(
            store=store,
            item_name=item_name,
            category=category,
            price=price,
            unit=unit,
            sale_type=sale_type,
            valid_from=date.fromisoformat(valid_from),
            valid_to=date.fromisoformat(valid_to),
            scraped_at=datetime.fromisoformat(scraped_at),
        )

    def get_latest_items(self) -> list[AdItem]:
        cur = self._conn.execute(
            "SELECT * FROM ad_items WHERE scrape_batch = (SELECT MAX(scrape_batch) FROM ad_items)"
        )
        return [self._parse_row(row) for row in cur.fetchall()]

    def _get_second_latest_batch(self) -> str | None:
        cur = self._conn.execute(
            "SELECT DISTINCT scrape_batch FROM ad_items ORDER BY scrape_batch DESC LIMIT 2"
        )
        batches = [r[0] for r in cur.fetchall()]
        return batches[1] if len(batches) == 2 else None

    def compute_diff(self) -> dict:
        latest = self.get_latest_items()
        prev_batch = self._get_second_latest_batch()
        if prev_batch is None:
            return {"new": latest, "changed": [], "dropped": []}

        cur = self._conn.execute(
            "SELECT * FROM ad_items WHERE scrape_batch = ?", (prev_batch,)
        )
        previous = [self._parse_row(row) for row in cur.fetchall()]

        prev_map = {(i.store, i.item_name, i.unit): i for i in previous}
        curr_map = {(i.store, i.item_name, i.unit): i for i in latest}

        new = [i for k, i in curr_map.items() if k not in prev_map]
        dropped = [i for k, i in prev_map.items() if k not in curr_map]
        changed = [
            {"item": curr_map[k], "old_price": prev_map[k].price}
            for k in curr_map
            if k in prev_map and curr_map[k].price != prev_map[k].price
        ]
        return {"new": new, "changed": changed, "dropped": dropped}
