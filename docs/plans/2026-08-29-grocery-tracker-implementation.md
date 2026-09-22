# Grocery Weekly Ad Tracker — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python scraper pipeline that pulls weekly grocery ad data, stores it in SQLite, writes `latest.json`, and exposes it to Home Assistant via `command_line` sensors for a tabbed Lovelace dashboard.

**Architecture:** Pure Python library (`grocery_ads/`) with zero HA dependencies. A thin `run.py` orchestrator calls each connector's `fetch() -> list[AdItem]`, persists results to SQLite, computes diffs, and writes `latest.json`. HA reads `latest.json` via `command_line` sensors. When ready for HACS, replace only `writer.py` with a `DataUpdateCoordinator`.

**Tech Stack:** Python 3.11+, `requests`, `pdfplumber`, `anthropic` SDK (LLM vision fallback), SQLite3 (stdlib), `pytest`, `responses` (HTTP mocking)

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `grocery_ads/__init__.py`
- Create: `grocery_ads/connectors/__init__.py`
- Create: `grocery_ads/parsers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/connectors/__init__.py`

**Step 1: Initialize git and create directory structure**

```bash
git init
mkdir -p grocery_ads/connectors grocery_ads/parsers tests/connectors docs/plans
touch grocery_ads/__init__.py grocery_ads/connectors/__init__.py grocery_ads/parsers/__init__.py
touch tests/__init__.py tests/connectors/__init__.py
```

**Step 2: Write `requirements.txt`**

```
requests>=2.31.0
pdfplumber>=0.10.0
anthropic>=0.34.0
responses>=0.25.0
pytest>=8.0.0
```

**Step 3: Write `.gitignore`**

```
groceries.db
latest.json
__pycache__/
*.pyc
.env
*.egg-info/
dist/
.pytest_cache/
```

**Step 4: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

**Step 5: Install dependencies**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error.

**Step 6: Commit**

```bash
git add .
git commit -m "chore: project scaffolding"
```

---

### Task 2: AdItem schema (`grocery_ads/schema.py`)

**Files:**
- Create: `grocery_ads/schema.py`
- Create: `tests/test_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_schema.py
from datetime import date, datetime
from grocery_ads.schema import AdItem

def test_aditem_creation():
    item = AdItem(
        store="hmart",
        item_name="Wagyu Beef",
        category="Meat",
        price=12.99,
        unit="lb",
        sale_type="sale",
        valid_from=date(2026, 8, 28),
        valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    assert item.store == "hmart"
    assert item.price == 12.99

def test_aditem_to_dict():
    item = AdItem(
        store="hmart",
        item_name="Wagyu Beef",
        category="Meat",
        price=12.99,
        unit="lb",
        sale_type="sale",
        valid_from=date(2026, 8, 28),
        valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )
    d = item.to_dict()
    assert d["store"] == "hmart"
    assert d["price"] == 12.99
    assert d["valid_from"] == "2026-08-28"
    assert d["valid_to"] == "2026-09-03"
    assert d["scraped_at"] == "2026-08-29T06:00:00"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_schema.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'grocery_ads.schema'`

**Step 3: Write minimal implementation**

```python
# grocery_ads/schema.py
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class AdItem:
    store: str
    item_name: str
    category: str
    price: float
    unit: str
    sale_type: str
    valid_from: date
    valid_to: date
    scraped_at: datetime
    # future hook: store_location_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "store": self.store,
            "item_name": self.item_name,
            "category": self.category,
            "price": self.price,
            "unit": self.unit,
            "sale_type": self.sale_type,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat(),
            "scraped_at": self.scraped_at.isoformat(),
        }
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_schema.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add grocery_ads/schema.py tests/test_schema.py
git commit -m "feat: AdItem schema with to_dict serialization"
```

---

### Task 3: SQLite layer (`grocery_ads/db.py`)

**Files:**
- Create: `grocery_ads/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing tests**

```python
# tests/test_db.py
import pytest
from datetime import date, datetime
from grocery_ads.db import Database
from grocery_ads.schema import AdItem


def make_item(store="hmart", name="Beef", price=10.0, valid_from=None, valid_to=None):
    return AdItem(
        store=store,
        item_name=name,
        category="Meat",
        price=price,
        unit="lb",
        sale_type="sale",
        valid_from=valid_from or date(2026, 8, 28),
        valid_to=valid_to or date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_insert_and_get_latest(db):
    items = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    db.insert_items(items)
    latest = db.get_latest_items()
    assert len(latest) == 2


def test_get_latest_returns_only_most_recent_scrape(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 9.0)]
    db.insert_items(old)
    db.insert_items(new)
    latest = db.get_latest_items()
    assert len(latest) == 1
    assert latest[0].price == 9.0


def test_diff_finds_new_items(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["new"]) == 1
    assert diff["new"][0].item_name == "Pork"


def test_diff_finds_price_changes(db):
    old = [make_item("hmart", "Beef", 10.0)]
    new = [make_item("hmart", "Beef", 9.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["item"].price == 9.0
    assert diff["changed"][0]["old_price"] == 10.0


def test_diff_finds_dropped_items(db):
    old = [make_item("hmart", "Beef", 10.0), make_item("hmart", "Pork", 8.0)]
    new = [make_item("hmart", "Beef", 10.0)]
    db.insert_items(old)
    db.insert_items(new)
    diff = db.compute_diff()
    assert len(diff["dropped"]) == 1
    assert diff["dropped"][0].item_name == "Pork"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_db.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'grocery_ads.db'`

**Step 3: Write minimal implementation**

```python
# grocery_ads/db.py
import sqlite3
from datetime import date, datetime
from pathlib import Path
from grocery_ads.schema import AdItem

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS ad_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_batch TEXT NOT NULL,
    store TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    unit TEXT NOT NULL,
    sale_type TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,
    scraped_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(_CREATE_SQL)
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

        prev_map = {(i.store, i.item_name): i for i in previous}
        curr_map = {(i.store, i.item_name): i for i in latest}

        new = [i for k, i in curr_map.items() if k not in prev_map]
        dropped = [i for k, i in prev_map.items() if k not in curr_map]
        changed = [
            {"item": curr_map[k], "old_price": prev_map[k].price}
            for k in curr_map
            if k in prev_map and curr_map[k].price != prev_map[k].price
        ]
        return {"new": new, "changed": changed, "dropped": dropped}
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_db.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add grocery_ads/db.py tests/test_db.py
git commit -m "feat: SQLite layer with insert and diff logic"
```

---

### Task 4: BaseConnector interface (`grocery_ads/connectors/base.py`)

**Files:**
- Create: `grocery_ads/connectors/base.py`
- Create: `tests/connectors/test_base.py`

**Step 1: Write the failing test**

```python
# tests/connectors/test_base.py
import pytest
from grocery_ads.connectors.base import BaseConnector


def test_cannot_instantiate_without_fetch():
    class BadConnector(BaseConnector):
        store_id = "bad"

    with pytest.raises(TypeError):
        BadConnector()


def test_can_instantiate_with_fetch():
    class GoodConnector(BaseConnector):
        store_id = "good"

        def fetch(self):
            return []

    connector = GoodConnector()
    assert connector.fetch() == []
```

**Step 2: Run to verify failure**

```bash
pytest tests/connectors/test_base.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# grocery_ads/connectors/base.py
from abc import ABC, abstractmethod
from grocery_ads.schema import AdItem


class BaseConnector(ABC):
    store_id: str

    @abstractmethod
    def fetch(self) -> list[AdItem]: ...
```

**Step 4: Run to verify pass**

```bash
pytest tests/connectors/test_base.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add grocery_ads/connectors/base.py tests/connectors/test_base.py
git commit -m "feat: BaseConnector abstract interface"
```

---

### Task 5: H Mart API discovery (exploratory — no TDD)

**Files:**
- Create: `scripts/discover_hmart.py` (temporary, gitignored after use)

**Goal:** Find the VTEX `productClusterId` for the weekly sale cluster.

**Step 1: Write discovery script**

```python
# scripts/discover_hmart.py
"""Run once to find H Mart's weekly sale productClusterId."""
import requests, json

BASE = "https://www.hmart.com/api/catalog_system/pub"

# Fetch available product clusters via facets
resp = requests.get(f"{BASE}/facets/search/", params={"map": "c"}, timeout=10)
print("Facets status:", resp.status_code)

# Search for products with "sale" in cluster highlights
resp2 = requests.get(
    f"{BASE}/products/search",
    params={"fq": "specificationFilter_40:true", "_from": 0, "_to": 4},
    timeout=10,
)
if resp2.ok:
    products = resp2.json()
    for p in products:
        print(p.get("productName"), p.get("clusterHighlights", {}))
else:
    print("Search failed:", resp2.status_code, resp2.text[:500])

# Also try fetching product clusters list
resp3 = requests.get(f"{BASE}/products/GetProductAndSkuIds", timeout=10)
print("Cluster endpoint status:", resp3.status_code)
```

**Step 2: Run discovery script**

```bash
mkdir -p scripts
python scripts/discover_hmart.py
```

Inspect the output. Look for cluster IDs associated with "Weekly Special", "On Sale", or similar labels in `clusterHighlights`. Note the numeric ID — you'll use it in the next task.

If no cluster ID is found via the facets API, try inspecting the H Mart website directly:
- Open `https://www.hmart.com/weekly-ads` in a browser
- Open DevTools → Network tab → filter for `XHR`
- Reload the page and look for requests to `/api/catalog_system/pub/products/search`
- Note the `fq=productClusterIds:{NUMBER}` parameter

**Step 3: Record the cluster ID**

Note the ID in a comment at the top of `connectors/hmart.py` (next task). Add `scripts/` to `.gitignore`.

```bash
echo "scripts/" >> .gitignore
```

---

### Task 6: H Mart connector (`grocery_ads/connectors/hmart.py`)

**Files:**
- Create: `grocery_ads/connectors/hmart.py`
- Create: `tests/connectors/test_hmart.py`

**Step 1: Write the failing test**

Use the `responses` library to mock VTEX API responses. Replace `CLUSTER_ID` below with the value found in Task 5.

```python
# tests/connectors/test_hmart.py
import pytest
import responses as rsps_lib
from datetime import date
from grocery_ads.connectors.hmart import HMartConnector

MOCK_VTEX_RESPONSE = [
    {
        "productName": "Wagyu Beef Sliced",
        "categories": ["/Meat/Beef/"],
        "clusterHighlights": {"99999": "Weekly Special"},
        "items": [
            {
                "measurementUnit": "lb",
                "sellers": [
                    {
                        "commertialOffer": {
                            "Price": 12.99,
                            "ListPrice": 15.99,
                        }
                    }
                ],
            }
        ],
        "validFrom": "2026-08-28T00:00:00",
        "validTo": "2026-09-03T23:59:59",
    }
]


@rsps_lib.activate
def test_fetch_returns_ad_items():
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=MOCK_VTEX_RESPONSE,
        status=200,
    )
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=[],  # empty page signals end of pagination
        status=200,
    )

    connector = HMartConnector()
    items = connector.fetch()

    assert len(items) == 1
    item = items[0]
    assert item.store == "hmart"
    assert item.item_name == "Wagyu Beef Sliced"
    assert item.price == 12.99
    assert item.sale_type == "sale"
    assert item.unit == "lb"
    assert item.category == "Meat/Beef"


@rsps_lib.activate
def test_fetch_handles_empty_response():
    rsps_lib.add(
        rsps_lib.GET,
        "https://www.hmart.com/api/catalog_system/pub/products/search",
        json=[],
        status=200,
    )
    connector = HMartConnector()
    assert connector.fetch() == []
```

**Step 2: Run to verify failure**

```bash
pytest tests/connectors/test_hmart.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Replace `WEEKLY_AD_CLUSTER_ID` with the value discovered in Task 5.

```python
# grocery_ads/connectors/hmart.py
from datetime import date, datetime
import requests
from grocery_ads.connectors.base import BaseConnector
from grocery_ads.schema import AdItem

WEEKLY_AD_CLUSTER_ID = "REPLACE_WITH_DISCOVERED_ID"
BASE_URL = "https://www.hmart.com/api/catalog_system/pub/products/search"
PAGE_SIZE = 50


class HMartConnector(BaseConnector):
    store_id = "hmart"

    def fetch(self) -> list[AdItem]:
        items = []
        offset = 0
        while True:
            resp = requests.get(
                BASE_URL,
                params={
                    "fq": f"productClusterIds:{WEEKLY_AD_CLUSTER_ID}",
                    "_from": offset,
                    "_to": offset + PAGE_SIZE - 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            page = resp.json()
            if not page:
                break
            for product in page:
                item = self._parse_product(product)
                if item:
                    items.append(item)
            offset += PAGE_SIZE
        return items

    def _parse_product(self, product: dict) -> AdItem | None:
        try:
            name = product["productName"]
            categories = product.get("categories", ["/Uncategorized/"])
            category = categories[0].strip("/").replace("/", "/") if categories else ""
            
            item_data = product.get("items", [{}])[0]
            seller = item_data.get("sellers", [{}])[0]
            offer = seller.get("commertialOffer", {})
            price = float(offer.get("Price", 0))
            list_price = float(offer.get("ListPrice", price))
            sale_type = "sale" if price < list_price else "regular"
            unit = item_data.get("measurementUnit", "ea")

            valid_from_str = product.get("validFrom", "")
            valid_to_str = product.get("validTo", "")
            valid_from = (
                datetime.fromisoformat(valid_from_str).date()
                if valid_from_str
                else date.today()
            )
            valid_to = (
                datetime.fromisoformat(valid_to_str).date()
                if valid_to_str
                else date.today()
            )

            return AdItem(
                store=self.store_id,
                item_name=name,
                category=category,
                price=price,
                unit=unit,
                sale_type=sale_type,
                valid_from=valid_from,
                valid_to=valid_to,
                scraped_at=datetime.now(),
            )
        except (KeyError, IndexError, ValueError):
            return None
```

**Step 4: Run to verify pass**

```bash
pytest tests/connectors/test_hmart.py -v
```
Expected: 2 PASSED

**Step 5: Run against live API to validate**

```bash
python -c "from grocery_ads.connectors.hmart import HMartConnector; items = HMartConnector().fetch(); print(f'{len(items)} items'); [print(i.item_name, i.price) for i in items[:5]]"
```

Expected: 10+ items printed. If 0 items, the cluster ID needs adjustment — re-run Task 5 discovery.

**Step 6: Commit**

```bash
git add grocery_ads/connectors/hmart.py tests/connectors/test_hmart.py
git commit -m "feat: H Mart VTEX JSON connector"
```

---

### Task 7: JSON writer (`grocery_ads/writer.py`)

**Files:**
- Create: `grocery_ads/writer.py`
- Create: `tests/test_writer.py`

**Step 1: Write the failing test**

```python
# tests/test_writer.py
import json
import pytest
from datetime import date, datetime
from pathlib import Path
from grocery_ads.schema import AdItem
from grocery_ads.writer import write_latest

def make_item(store, name, price):
    return AdItem(
        store=store, item_name=name, category="Produce", price=price,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


def test_write_latest_creates_json(tmp_path):
    items = [
        make_item("hmart", "Apple", 1.99),
        make_item("hmart", "Banana", 0.49),
        make_item("99ranch", "Apple", 1.79),
    ]
    diff = {"new": [make_item("hmart", "Banana", 0.49)], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path)

    data = json.loads(out_path.read_text())
    assert "hmart" in data
    assert len(data["hmart"]) == 2
    assert "99ranch" in data
    assert "diff" in data
    assert "lowest_price" in data
    assert "scraped_at" in data


def test_lowest_price_computed_correctly(tmp_path):
    items = [
        make_item("hmart", "Apple", 1.99),
        make_item("99ranch", "Apple", 1.79),
    ]
    diff = {"new": [], "changed": [], "dropped": []}
    out_path = tmp_path / "latest.json"

    write_latest(items, diff, out_path)

    data = json.loads(out_path.read_text())
    assert data["lowest_price"]["Apple"]["price"] == 1.79
    assert data["lowest_price"]["Apple"]["store"] == "99ranch"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_writer.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# grocery_ads/writer.py
import json
from datetime import datetime
from pathlib import Path
from grocery_ads.schema import AdItem


def write_latest(items: list[AdItem], diff: dict, path: str | Path) -> None:
    by_store: dict[str, list] = {}
    for item in items:
        by_store.setdefault(item.store, []).append(item.to_dict())

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
        "scraped_at": datetime.now().isoformat(),
    }

    Path(path).write_text(json.dumps(output, indent=2))
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_writer.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add grocery_ads/writer.py tests/test_writer.py
git commit -m "feat: JSON writer with lowest-price and diff output"
```

---

### Task 8: Orchestrator (`run.py`)

**Files:**
- Create: `run.py`
- Create: `tests/test_run.py`

**Step 1: Write the failing test**

```python
# tests/test_run.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from pathlib import Path
from grocery_ads.schema import AdItem


def make_item(store="hmart", name="Beef"):
    return AdItem(
        store=store, item_name=name, category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


def test_run_calls_all_connectors(tmp_path):
    from run import run

    mock_items = [make_item()]
    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        mock_connector = MagicMock()
        mock_connector.fetch.return_value = mock_items
        mock_connectors.__iter__ = MagicMock(return_value=iter([mock_connector]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = mock_items
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")

        mock_connector.fetch.assert_called_once()
        mock_db.insert_items.assert_called_once()
        mock_write.assert_called_once()


def test_run_continues_if_one_connector_fails(tmp_path):
    from run import run

    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest"):

        bad = MagicMock()
        bad.fetch.side_effect = Exception("network error")
        good = MagicMock()
        good.fetch.return_value = [make_item()]
        mock_connectors.__iter__ = MagicMock(return_value=iter([bad, good]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = [make_item()]
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")
        good.fetch.assert_called_once()
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_run.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'run'`

**Step 3: Write minimal implementation**

```python
# run.py
import argparse
import sys
from pathlib import Path
from grocery_ads.connectors.hmart import HMartConnector
from grocery_ads.db import Database
from grocery_ads.writer import write_latest

CONNECTORS = [
    HMartConnector(),
]

DB_PATH = Path("groceries.db")
JSON_PATH = Path("latest.json")


def run(db_path: Path = DB_PATH, json_path: Path = JSON_PATH, stores: list[str] | None = None, dry_run: bool = False) -> int:
    db = Database(db_path)
    all_items = []
    failed = 0

    for connector in CONNECTORS:
        if stores and connector.store_id not in stores:
            continue
        try:
            items = connector.fetch()
            print(f"[{connector.store_id}] fetched {len(items)} items")
            all_items.extend(items)
        except Exception as e:
            print(f"[{connector.store_id}] ERROR: {e}", file=sys.stderr)
            failed += 1

    if not all_items:
        print("No items fetched — all connectors failed.", file=sys.stderr)
        return 1

    if not dry_run:
        db.insert_items(all_items)
        diff = db.compute_diff()
        write_latest(db.get_latest_items(), diff, json_path)
        print(f"Wrote {json_path}")
    else:
        for item in all_items:
            print(item)

    return 1 if failed == len(CONNECTORS) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", help="Comma-separated store IDs to run")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stores = args.stores.split(",") if args.stores else None
    sys.exit(run(stores=stores, dry_run=args.dry_run))
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_run.py -v
```
Expected: 2 PASSED

**Step 5: Run full pipeline against live H Mart API**

```bash
python run.py --stores hmart --dry-run
```

Expected: list of H Mart items printed to stdout, no db/json written.

```bash
python run.py --stores hmart
```

Expected: `groceries.db` created, `latest.json` written with `hmart` key populated.

**Step 6: Commit**

```bash
git add run.py tests/test_run.py
git commit -m "feat: run.py orchestrator with per-connector error isolation"
```

---

### Task 9: Home Assistant sensor configuration

**Files:**
- Create: `ha_config/sensors.yaml` (reference config — copy into your HA config manually)

**Step 1: Write sensor config**

Replace `/path/to/latest.json` with the actual path where `latest.json` will live (must be accessible to the HA process — e.g. `/config/grocery_ads/latest.json` or a symlink).

```yaml
# ha_config/sensors.yaml
command_line:
  - sensor:
      name: Grocery Ads HMart
      unique_id: grocery_ads_hmart
      command: >
        python3 -c "import sys,json; d=json.load(open('/path/to/latest.json')); print(json.dumps(d.get('hmart',[])))"
      value_template: "{{ value_json | length }} items"
      json_attributes_template: "{{ value_json }}"
      scan_interval: 3600

  - sensor:
      name: Grocery Ads Diff
      unique_id: grocery_ads_diff
      command: >
        python3 -c "import sys,json; d=json.load(open('/path/to/latest.json')); print(json.dumps(d.get('diff',{})))"
      value_template: "{{ value_json.new | length }} new"
      json_attributes_template: "{{ value_json }}"
      scan_interval: 3600

  - sensor:
      name: Grocery Ads Lowest Price
      unique_id: grocery_ads_lowest_price
      command: >
        python3 -c "import sys,json; d=json.load(open('/path/to/latest.json')); print(json.dumps(d.get('lowest_price',{})))"
      value_template: "{{ value_json | length }} items tracked"
      json_attributes_template: "{{ value_json }}"
      scan_interval: 3600
```

**Step 2: Place `latest.json` where HA can read it**

Option A — symlink into HA config dir (if running on same machine):
```bash
ln -s /path/to/project/latest.json /path/to/ha/config/grocery_ads/latest.json
```

Option B — set `json_path` in `run.py` to write directly into HA config dir.

**Step 3: Add sensors to HA and check config**

Copy sensor config into your HA `configuration.yaml` (or a `!include`d file), then:

In HA UI: Developer Tools → YAML → Check Configuration. Fix any errors.

**Step 4: Reload HA**

In HA UI: Developer Tools → YAML → Reload All YAML Configuration.

Check that `sensor.grocery_ads_hmart` appears in Developer Tools → States with `X items` as its state.

**Step 5: Commit reference config**

```bash
git add ha_config/sensors.yaml
git commit -m "docs: HA command_line sensor reference config"
```

---

### Task 10: Lovelace dashboard (tabbed view)

**Files:**
- Create: `ha_config/dashboard.yaml` (reference — add via HA UI)

**Step 1: Write dashboard YAML**

```yaml
# ha_config/dashboard.yaml
title: Grocery Ads
views:
  - title: Raw Feed
    path: raw-feed
    cards:
      - type: markdown
        title: H Mart This Week
        content: >
          {% set items = state_attr('sensor.grocery_ads_hmart', 'items') or [] %}
          {% for item in items %}
          **{{ item.item_name }}** — ${{ item.price }} / {{ item.unit }} ({{ item.sale_type }})
          {% endfor %}

  - title: Lowest Prices
    path: lowest-prices
    cards:
      - type: markdown
        title: Best Price Per Item
        content: >
          {% set lp = state_attr('sensor.grocery_ads_lowest_price', 'items') or {} %}
          {% for name, info in lp.items() %}
          **{{ name }}** — ${{ info.price }} @ {{ info.store }}
          {% endfor %}

  - title: New Deals
    path: new-deals
    cards:
      - type: markdown
        title: New This Week
        content: >
          {% set diff = state_attr('sensor.grocery_ads_diff', 'items') or {} %}
          {% for item in diff.new or [] %}
          **{{ item.item_name }}** — ${{ item.price }} ({{ item.store }})
          {% endfor %}
          {% for change in diff.changed or [] %}
          **{{ change.item.item_name }}** — ${{ change.old_price }} → ${{ change.item.price }}
          {% endfor %}
```

**Step 2: Add dashboard in HA**

In HA UI: Settings → Dashboards → Add Dashboard → "Grocery Ads", then switch to YAML edit mode and paste the config above.

**Step 3: Validate all 3 tabs show data**

Confirm the Raw Feed tab shows H Mart items, Lowest Prices shows cross-store comparison, New Deals shows this week's new/changed items.

**Step 4: Commit**

```bash
git add ha_config/dashboard.yaml
git commit -m "docs: Lovelace tabbed dashboard reference config"
```

---

### Task 11: 99 Ranch investigation + connector

**Files:**
- Create: `scripts/discover_ranch99.py` (temporary)
- Create: `grocery_ads/connectors/ranch99.py`
- Create: `tests/connectors/test_ranch99.py`

**Step 1: Write discovery script**

```python
# scripts/discover_ranch99.py
"""Inspect 99 Ranch ad backend — JSON API or PDF/image?"""
import requests

headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get("https://h5.awsprod.99ranch.com/stores/ad/1", headers=headers, timeout=10)
print("Status:", resp.status_code)
print("Content-Type:", resp.headers.get("content-type"))
print("Body preview:", resp.text[:2000])
```

**Step 2: Run and interpret**

```bash
python scripts/discover_ranch99.py
```

- If response is JSON: build a JSON connector (similar to H Mart, adapt field names)
- If response is HTML with `<img>` or iframe: it's image-based — use `pdf_parser.py` with LLM vision
- If response redirects to a PDF URL: use `pdf_parser.py` text path

**Step 3: Implement connector based on findings**

If JSON path — write a `Ranch99Connector` similar to `HMartConnector`, with tests using `responses` library mock.

If PDF/image path — stub the connector to call `pdf_parser.py` (built in Task 12), write a test that mocks the parser call.

**Step 4: Add to `run.py` CONNECTORS list**

```python
from grocery_ads.connectors.ranch99 import Ranch99Connector

CONNECTORS = [
    HMartConnector(),
    Ranch99Connector(),
]
```

**Step 5: Commit**

```bash
git add grocery_ads/connectors/ranch99.py tests/connectors/test_ranch99.py run.py
git commit -m "feat: 99 Ranch connector"
```

---

### Task 12: Shared PDF parser (`grocery_ads/parsers/pdf_parser.py`)

**Files:**
- Create: `grocery_ads/parsers/pdf_parser.py`
- Create: `tests/parsers/test_pdf_parser.py`
- Create: `tests/parsers/__init__.py`
- Create: `tests/parsers/fixtures/sample.pdf` (generate in step 1)

**Step 1: Generate a minimal test PDF**

```python
# run this once to create the fixture
import pdfplumber
# Use any available PDF or create a simple one with fpdf2:
# pip install fpdf2
from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.cell(200, 10, txt="Fuji Apples  $1.99/lb  Sale", ln=True)
pdf.cell(200, 10, txt="Chicken Thighs  $2.49/lb  BOGO", ln=True)
pdf.output("tests/parsers/fixtures/sample.pdf")
print("fixture written")
```

```bash
mkdir -p tests/parsers/fixtures
python -c "
from fpdf import FPDF
pdf = FPDF(); pdf.add_page(); pdf.set_font('Helvetica', size=12)
pdf.cell(200, 10, txt='Fuji Apples  \$1.99/lb  Sale', ln=True)
pdf.cell(200, 10, txt='Chicken Thighs  \$2.49/lb  BOGO', ln=True)
pdf.output('tests/parsers/fixtures/sample.pdf')
print('written')
"
pip install fpdf2
```

**Step 2: Write the failing tests**

```python
# tests/parsers/test_pdf_parser.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from grocery_ads.parsers.pdf_parser import parse_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_parse_pdf_text_path_returns_items():
    items = parse_pdf(FIXTURE, store="uwajimaya")
    assert len(items) >= 1
    assert all(hasattr(i, "item_name") for i in items)
    assert all(i.store == "uwajimaya" for i in items)


def test_parse_pdf_calls_llm_when_no_text(tmp_path):
    empty_pdf = tmp_path / "empty.pdf"
    # Create a PDF with no embedded text (image-only simulation via mock)
    with patch("grocery_ads.parsers.pdf_parser._extract_text") as mock_extract, \
         patch("grocery_ads.parsers.pdf_parser._llm_vision_parse") as mock_llm:
        mock_extract.return_value = ""
        mock_llm.return_value = [
            {"item_name": "Salmon", "price": "8.99", "unit": "lb", "sale_type": "sale"}
        ]
        items = parse_pdf(FIXTURE, store="uwajimaya")
        mock_llm.assert_called_once()
        assert items[0].item_name == "Salmon"
```

**Step 3: Run to verify failure**

```bash
pytest tests/parsers/test_pdf_parser.py -v
```

**Step 4: Write minimal implementation**

```python
# grocery_ads/parsers/pdf_parser.py
import json
import re
from datetime import date, datetime
from pathlib import Path
import pdfplumber
from grocery_ads.schema import AdItem

_PRICE_RE = re.compile(r"\$?([\d]+\.[\d]{2})")


def _extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _llm_vision_parse(pdf_path: Path) -> list[dict]:
    import anthropic, base64
    client = anthropic.Anthropic()
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.standard_b64encode(f.read()).decode()

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all grocery sale items from this weekly ad flyer. "
                            "Return a JSON array where each element has: "
                            "item_name (string), price (string like '1.99'), "
                            "unit (string like 'lb', 'ea', '12oz'), "
                            "sale_type (string: 'sale', 'bogo', or 'member price'). "
                            "Return ONLY the JSON array, no other text."
                        ),
                    },
                ],
            }
        ],
    )
    return json.loads(message.content[0].text)


def _parse_text_items(text: str, store: str) -> list[AdItem]:
    items = []
    for line in text.splitlines():
        price_match = _PRICE_RE.search(line)
        if not price_match:
            continue
        price = float(price_match.group(1))
        name = line[: price_match.start()].strip().rstrip("$").strip()
        if not name:
            continue
        unit = "ea"
        for candidate in ["lb", "oz", "kg", "ea", "pk"]:
            if candidate in line.lower():
                unit = candidate
                break
        sale_type = "bogo" if "bogo" in line.lower() else "sale"
        items.append(
            AdItem(
                store=store,
                item_name=name,
                category="",
                price=price,
                unit=unit,
                sale_type=sale_type,
                valid_from=date.today(),
                valid_to=date.today(),
                scraped_at=datetime.now(),
            )
        )
    return items


def parse_pdf(pdf_path: str | Path, store: str, valid_from: date | None = None, valid_to: date | None = None) -> list[AdItem]:
    pdf_path = Path(pdf_path)
    text = _extract_text(pdf_path)

    if text.strip():
        return _parse_text_items(text, store)

    raw = _llm_vision_parse(pdf_path)
    return [
        AdItem(
            store=store,
            item_name=r["item_name"],
            category="",
            price=float(r["price"]),
            unit=r.get("unit", "ea"),
            sale_type=r.get("sale_type", "sale"),
            valid_from=valid_from or date.today(),
            valid_to=valid_to or date.today(),
            scraped_at=datetime.now(),
        )
        for r in raw
    ]
```

**Step 5: Run to verify pass**

```bash
pytest tests/parsers/ -v
```
Expected: 2 PASSED

**Step 6: Commit**

```bash
git add grocery_ads/parsers/pdf_parser.py tests/parsers/ 
git commit -m "feat: shared PDF parser with pdfplumber + LLM vision fallback"
```

---

### Task 13: PDF store connectors (Uwajimaya, Zupan's, New Seasons)

**Files:**
- Create: `grocery_ads/connectors/uwajimaya.py`
- Create: `grocery_ads/connectors/zupans.py`
- Create: `grocery_ads/connectors/new_seasons.py`
- Create: `tests/connectors/test_pdf_connectors.py`

Each PDF connector follows the same pattern — find the current PDF URL, download it, pass to `pdf_parser.parse_pdf()`. Before writing each connector, do a quick devtools check on the store's weekly ad page to confirm PDF vs. flipbook.

**Step 1: Write shared test pattern**

```python
# tests/connectors/test_pdf_connectors.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from grocery_ads.schema import AdItem

def make_mock_items(store):
    return [AdItem(store=store, item_name="Apple", category="Produce",
                   price=1.99, unit="lb", sale_type="sale",
                   valid_from=date.today(), valid_to=date.today(),
                   scraped_at=datetime.now())]

def test_uwajimaya_fetch():
    from grocery_ads.connectors.uwajimaya import UwajimayaConnector
    with patch("grocery_ads.connectors.uwajimaya.parse_pdf") as mock_parse, \
         patch("grocery_ads.connectors.uwajimaya.requests.get") as mock_get:
        mock_get.return_value.content = b"%PDF fake"
        mock_get.return_value.raise_for_status = MagicMock()
        mock_parse.return_value = make_mock_items("uwajimaya")
        items = UwajimayaConnector().fetch()
        assert items[0].store == "uwajimaya"

def test_zupans_fetch():
    from grocery_ads.connectors.zupans import ZupansConnector
    with patch("grocery_ads.connectors.zupans.parse_pdf") as mock_parse, \
         patch("grocery_ads.connectors.zupans.requests.get") as mock_get:
        mock_get.return_value.content = b"%PDF fake"
        mock_get.return_value.raise_for_status = MagicMock()
        mock_parse.return_value = make_mock_items("zupans")
        items = ZupansConnector().fetch()
        assert items[0].store == "zupans"

def test_new_seasons_fetch():
    from grocery_ads.connectors.new_seasons import NewSeasonsConnector
    with patch("grocery_ads.connectors.new_seasons.parse_pdf") as mock_parse, \
         patch("grocery_ads.connectors.new_seasons.requests.get") as mock_get:
        mock_get.return_value.content = b"%PDF fake"
        mock_get.return_value.raise_for_status = MagicMock()
        mock_parse.return_value = make_mock_items("new_seasons")
        items = NewSeasonsConnector().fetch()
        assert items[0].store == "new_seasons"
```

**Step 2: Implement each connector (same pattern, different URL)**

Before coding each, confirm the PDF URL by visiting the store's weekly ad page and inspecting network requests for a `.pdf` link.

```python
# grocery_ads/connectors/uwajimaya.py  (repeat pattern for zupans, new_seasons)
import tempfile
from pathlib import Path
import requests
from grocery_ads.connectors.base import BaseConnector
from grocery_ads.parsers.pdf_parser import parse_pdf
from grocery_ads.schema import AdItem

WEEKLY_AD_URL = "https://www.uwajimaya.com/weekly-ad"  # confirm actual PDF URL via devtools


class UwajimayaConnector(BaseConnector):
    store_id = "uwajimaya"

    def fetch(self) -> list[AdItem]:
        pdf_url = self._find_pdf_url()
        resp = requests.get(pdf_url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            tmp_path = Path(f.name)
        try:
            return parse_pdf(tmp_path, store=self.store_id)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _find_pdf_url(self) -> str:
        # Inspect the weekly ad page for a direct PDF link
        # Replace this with the actual PDF URL once confirmed
        return WEEKLY_AD_URL
```

**Step 3: Run tests**

```bash
pytest tests/connectors/test_pdf_connectors.py -v
```
Expected: 3 PASSED

**Step 4: Add all connectors to `run.py`**

```python
from grocery_ads.connectors.uwajimaya import UwajimayaConnector
from grocery_ads.connectors.zupans import ZupansConnector
from grocery_ads.connectors.new_seasons import NewSeasonsConnector

CONNECTORS = [
    HMartConnector(),
    Ranch99Connector(),
    UwajimayaConnector(),
    ZupansConnector(),
    NewSeasonsConnector(),
]
```

**Step 5: Run full pipeline dry-run**

```bash
python run.py --dry-run
```

Expected: items from all 5 stores printed.

**Step 6: Commit**

```bash
git add grocery_ads/connectors/ tests/connectors/test_pdf_connectors.py run.py
git commit -m "feat: Uwajimaya, Zupan's, New Seasons PDF connectors"
```

---

### Task 14: Set up cron + final validation

**Step 1: Set absolute paths in `run.py`**

Edit `DB_PATH` and `JSON_PATH` in `run.py` to point to the real filesystem locations.

**Step 2: Add crontab entries**

```bash
crontab -e
```

Add:
```
0 6 * * 3 /path/to/.venv/bin/python /path/to/run.py >> /path/to/logs/grocery.log 2>&1
0 6 * * 4 /path/to/.venv/bin/python /path/to/run.py >> /path/to/logs/grocery.log 2>&1
```

**Step 3: Run full pipeline once manually**

```bash
python run.py
cat latest.json | python3 -m json.tool | head -50
```

Confirm `latest.json` has data for all working stores.

**Step 4: Verify HA sensors update**

In HA: Developer Tools → States → search `grocery_ads` — confirm sensors show item counts.

**Step 5: Final commit**

```bash
git add -u
git commit -m "chore: final cron config and path settings"
```

---

## Future: HACS Migration Notes

When ready to package as a HACS integration:

1. Create `custom_components/grocery_ads/` with `manifest.json`, `config_flow.py`, `coordinator.py`
2. `coordinator.py` subclasses `DataUpdateCoordinator`, imports `grocery_ads.connectors.*`, calls `fetch()` — no connector changes
3. `config_flow.py` adds UI for store selection; later adds zip code lookup via a store-location registry
4. Store location registry: a JSON file mapping zip codes to nearby stores (build once, update as chains expand)
5. Publish to HACS by adding `hacs.json` and a GitHub release
