# Grocery Weekly Ad Tracker — Design Doc
**Date:** 2026-08-29  
**Status:** Approved

## Goal

A Python scraper pipeline that pulls weekly ad data from regional grocery chains, normalizes it into a common schema, persists it to SQLite, and exposes it to Home Assistant via `command_line` sensors for a tabbed Lovelace dashboard.

Long-term target: package as a HACS custom_component with store suggestion by zip code. Architecture is designed to support this migration without rewriting the connector layer.

## Chosen Approach: Clean library + thin orchestration layer

Pure Python library (`grocery_ads/`) with zero Home Assistant dependencies. A thin `run.py` orchestrator writes `latest.json` for HA to read now. When ready for HACS, a `DataUpdateCoordinator` imports the same library — migration is a new file, not a rewrite.

## Project Structure

```
grocery_ads/
  connectors/
    base.py           # BaseConnector ABC: fetch() -> list[AdItem]
    hmart.py          # VTEX JSON connector (build first)
    ranch99.py        # JSON or PDF, TBD after network inspection
    uwajimaya.py
    zupans.py
    new_seasons.py
  parsers/
    pdf_parser.py     # shared pdfplumber + LLM-vision fallback
  schema.py           # AdItem dataclass
  db.py               # SQLite read/write + diff logic
  writer.py           # writes latest.json

run.py                # CLI orchestrator
groceries.db          # SQLite history (gitignored)
latest.json           # current week snapshot (read by HA)
docs/plans/
requirements.txt
```

## Data Schema

```python
@dataclass
class AdItem:
    store: str          # "hmart", "99ranch", "uwajimaya", etc.
    item_name: str
    category: str       # best-effort; empty string if unavailable
    price: float
    unit: str           # "lb", "ea", "12oz", etc.
    sale_type: str      # "sale", "bogo", "member price"
    valid_from: date
    valid_to: date
    scraped_at: datetime
    # future: store_location_id: str | None = None  (zipcode feature hook)
```

## SQLite Layer

Two tables in `groceries.db`:

- **`ad_items`** — full scrape history, append-only. One row per item per scrape run.
- **`ad_diff`** — computed each run: new items, changed prices, dropped items vs. prior scrape. Set comparison on `(store, item_name, valid_from)`.

## `latest.json` Structure

Pre-computed at write time so HA sensors read one key each with no template logic:

```json
{
  "hmart": [...],
  "99ranch": [...],
  "uwajimaya": [...],
  "zupans": [...],
  "new_seasons": [...],
  "diff": [...],
  "lowest_price": { "item_name": { "store": "...", "price": 0.00 } },
  "scraped_at": "2026-08-29T06:00:00"
}
```

## Connector Interface

```python
class BaseConnector(ABC):
    store_id: str  # class-level constant

    @abstractmethod
    def fetch(self) -> list[AdItem]: ...
```

Each connector fetches, parses, and returns normalized `AdItem` objects. No shared state, no side effects. Adding a new store = one new file.

### H Mart (VTEX JSON)
- Endpoint: `https://www.hmart.com/api/catalog_system/pub/products/search`
- Query param: `fq=productClusterIds:{id}` — weekly sale cluster ID to be found via API probing in code (not manual devtools)
- Paginated via `_from` / `_to`; connector pages until exhausted
- `sellingPrice` → `price`; `sale_type = "sale"` when it differs from `priceWithoutDiscount`

### PDF-based stores (Uwajimaya, Zupan's, New Seasons)
- `pdf_parser.py` attempts `pdfplumber` text extraction first
- Falls back to Claude API vision (one call per page) if no embedded text layer
- Both paths return the same `list[AdItem]` — connectors don't need to know which path ran

### 99 Ranch
- Inspect `h5.awsprod.99ranch.com` network traffic first; use JSON path if available, PDF path otherwise

## Orchestrator (`run.py`)

```
python run.py [--stores hmart,99ranch,...] [--dry-run]
```

- Calls `fetch()` on each enabled connector
- Writes results to SQLite, computes diff, writes `latest.json`
- `--dry-run` prints without writing
- Non-zero exit if all connectors fail (cron-alertable)

### Cron schedule (two runs to catch Wed + Thu rotation)
```
0 6 * * 3 cd /path/to/project && python run.py
0 6 * * 4 cd /path/to/project && python run.py
```

## Home Assistant Integration

One `command_line` sensor per store + one for `diff` + one for `lowest_price`, all reading from `latest.json`. Lovelace tabbed dashboard uses `markdown` cards templated from sensor attributes.

```yaml
command_line:
  - sensor:
      name: Grocery Ads HMart
      command: "cat /path/to/latest.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('hmart',[])))\" "
      value_template: "{{ value_json | length }} items"
      json_attributes_template: "{{ value_json }}"
      scan_interval: 3600
```

## Future: HACS Migration Path

When ready:
1. Create `custom_components/grocery_ads/` shell
2. Write a `DataUpdateCoordinator` that imports `grocery_ads.connectors.*` and calls `fetch()`
3. Replace `writer.py` with coordinator data push to HA state machine
4. Add `config_flow` for store selection; later, zip code lookup for store suggestions
5. No connector code changes required

## Build Order

1. `schema.py`, `db.py` — data layer first, validates the schema
2. `connectors/hmart.py` — VTEX JSON, end-to-end pipeline validation
3. `writer.py` + `run.py` — orchestrator + JSON output
4. HA sensor wiring + Lovelace dashboard
5. Investigate 99 Ranch backend; build `connectors/ranch99.py`
6. `parsers/pdf_parser.py` — shared PDF/LLM-vision module
7. `connectors/uwajimaya.py`, `connectors/zupans.py`, `connectors/new_seasons.py`
