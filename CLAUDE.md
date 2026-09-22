# Grocery Weekly Ad Tracker — Project Brief

## Goal
Build a Python-based scraper/parser pipeline that pulls weekly ad/sale data from
a set of regional grocery chains, normalizes it into a common schema, and
exposes it to Home Assistant via a custom HACS integration for a tabbed
Lovelace dashboard.

## Target stores
- H Mart
- 99 Ranch Market
- Uwajimaya
- Zupan's Markets
- New Seasons Market

Open to adding more stores later, but the pipeline should be built so adding a
new store means writing one new "connector" module, not touching the rest of
the system.

## Dashboard requirements
Tabbed presentation covering all of the following views, all built from the
same underlying dataset:
1. **Raw feed** — current week's ad items per store
2. **Lowest price per item across stores** — cross-store comparison
3. **New/changed deals this week** — diff vs. last week's scrape
4. **Category browsing** — produce, meat, dairy, etc.

## Architecture

The project ships as a Home Assistant HACS custom integration —
`custom_components/grocery_ads/` — installed via Settings -> Devices &
Services -> Add Integration, one config entry per store, rather than a
standalone script run from cron. Each store's connector runs inside a
`DataUpdateCoordinator` on HA's own update loop; H Mart and Zupan's (the
two structured stores) also feed a shared `AggregateCoordinator` that
computes the lowest-price and new-deals views. See
`docs/plans/2026-09-21-hacs-integration-design.md` for the full design
(entity/device layout, coordinator lifecycle, config flow) rather than
duplicating it here.

```
custom_components/grocery_ads/
  connectors/            # same per-store modules as before, unchanged logic
    hmart.py                # VTEX JSON API -> AdItem (structured)
    zupans.py                # WordPress REST API (HTML fragment) -> AdItem (structured)
    ranch99.py                 # scrapes __NEXT_DATA__ for flyer image URLs -> FlyerRef
    uwajimaya.py                 # scrapes weekly-specials page for PDF URL -> FlyerRef
    new_seasons.py                # scrapes /weekly-ad page for PDF URL -> FlyerRef
    base.py                        # BaseConnector (AdItem) + FlyerConnector (FlyerRef) interfaces
  const.py                # DOMAIN, STORE_REGISTRY (store metadata + kind)
  config_flow.py            # UI setup: pick a store per config entry, dup-entry guard
  coordinator.py              # GroceryAdsCoordinator + AggregateCoordinator
  sensor.py                     # GroceryAdsStoreSensor + the two aggregate sensors
  __init__.py                     # entry setup/unload, aggregate-coordinator lifecycle
  schema.py                         # AdItem + FlyerRef dataclasses
  db.py                              # SQLite read/write + diff logic
  manifest.json                       # HA integration manifest
hacs.json              # HACS repository metadata
ha_config/
  dashboard.yaml        # tabbed Lovelace dashboard reference config
```

`ha_config/sensors.yaml` (the old `command_line` sensor config) and the
cron schedule it depended on are retired — the integration owns polling
via each coordinator's update interval, and `latest.json`/`run.py` are no
longer part of the production path.

**Two connector shapes, decided 2026-09-21:** most of these stores don't
expose per-item text data — three of the five just publish a flyer as a
PDF or a set of flipbook images with no embedded item data. Rather than
building OCR/LLM-vision extraction for those, `FlyerConnector` connectors
just locate the current flyer URL(s) and the dashboard displays it
directly (inline image, or a link to the PDF). Only stores with genuine
structured data (H Mart's JSON API, Zupan's HTML-fragment REST endpoint)
go through `BaseConnector` and produce real `AdItem`s — those are the only
two that participate in the Lowest Price / New Deals / Category tabs.

## Common data schema

Every connector must normalize its output to:

```
store        text   -- e.g. "hmart", "99ranch", "uwajimaya"
item_name    text
category     text   -- best-effort; not all sources will have clean categories
price        real
unit         text   -- e.g. "lb", "ea", "12oz"
sale_type    text   -- e.g. "sale", "bogo", "member price"
valid_from   date
valid_to     date
scraped_at   timestamp
```

Store this in SQLite (`groceries.db`) for history (needed for the "diff"
tab).

## Per-store research findings (as of 2026-09-21)

### H Mart — CONFIRMED, structured (`BaseConnector`)
- VTEX JSON search API, `productClusterIds:208` is the weekly-sale cluster.
- No auth required. Paginated via `_from`/`_to`, total read from the
  `resources` response header.
- `custom_components/grocery_ads/connectors/hmart.py`.

### Zupan's Markets — CONFIRMED, structured (`BaseConnector`)
- Not a flyer at all — turned out to have real structured data.
- `GET https://www.zupans.com/wp-json/wp/v2/promotions?slug=whats-on-sale`
  (WordPress REST API, static URL, no auth) returns an HTML fragment
  (`content.rendered`) with one `<article>` per sale item. Parsed with
  BeautifulSoup: `h3` = name, `p.link` = price/unit, `p.micro` = tags
  (used to flag `"member price"`). Validity comes from an `<h2>Through
  <Month> <Day></h2>` heading, year inferred from the `modified` field.
- `category` is left empty — the page doesn't separate items by
  department, so there's nothing better than best-effort here.
- `custom_components/grocery_ads/connectors/zupans.py`.

### 99 Ranch Market — CONFIRMED, flyer (`FlyerConnector`)
- No item-level JSON API exists (checked, including Next.js `/_next/data/`
  routes — 404). The weekly ad is a set of per-category flyer JPEGs.
- `GET https://www.99ranch.com/stores/promotions/{storeId}` embeds a
  `<script id="__NEXT_DATA__">` JSON blob at
  `props.pageProps.detail.storeActivities`, a list of
  `{name, date, imageUrl}` — one entry per flyer category page.
- The config flow collects a per-config-entry `location_id` for 99 Ranch
  (`STORE_REGISTRY["99ranch"]["needs_location"]` is the only `True` entry),
  wired through to `Ranch99Connector` via `DEFAULT_LOCATION_ID` as a
  constructor default (commit `5111a0f`). Users still have to know/find
  the numeric location ID themselves — resolving a zip code to that ID
  automatically is not built.
- `custom_components/grocery_ads/connectors/ranch99.py`.

### Uwajimaya — CONFIRMED, flyer (`FlyerConnector`)
- `https://www.uwajimaya.com/weekly-specials/` has a real PDF text layer
  (not scanned/flipbook) but per user direction (2026-09-21) it's not
  parsed — just linked directly.
- PDF URL is under `a.button-bar.blue[href$=".pdf"]` inside
  `div.section-button`; filename embeds the ad start date
  (`WeeklyAd-MM.DD.YY.pdf`), not a stable path — must scrape the page
  each run.
- Cloudflare blocks `requests`' bare `User-Agent`; needs a full
  browser-like header set (see `BROWSER_HEADERS` in `connectors/base.py`).
- `custom_components/grocery_ads/connectors/uwajimaya.py`.

### New Seasons Market — CONFIRMED, flyer (`FlyerConnector`)
- `https://www.newseasonsmarket.com/weekly-ad` links a PDF via a CMS
  content-asset URL (`getContentAsset/<uuid>/<uuid>/NSM-Sales-Flyer-
  MMDDYY-MMDDYY-(R).pdf`) — the date range is embedded in the filename.
  Not a stable path — must scrape the page each run.
- `custom_components/grocery_ads/connectors/new_seasons.py`.

## Build order (complete)
1. ~~`connectors/hmart.py`~~ — done.
2. ~~Investigate 99 Ranch's backend~~ — done; no JSON item API exists, built
   as a flyer connector instead.
3. ~~`connectors/uwajimaya.py`, `connectors/zupans.py`,
   `connectors/new_seasons.py`~~ — done (Zupan's structured, the other two
   as flyer connectors — no shared PDF parser needed per the flyer
   decision above).
4. ~~`run.py` orchestrator~~ — done; runs both `CONNECTORS` (AdItem) and
   `FLYER_CONNECTORS` (FlyerRef) with per-connector error isolation.
5. ~~Home Assistant integration~~ — `custom_components/grocery_ads/`, a
   HACS custom integration with a config-flow-driven setup and per-store
   `DataUpdateCoordinator`s, replacing the earlier cron/`command_line`
   design (see `docs/plans/2026-09-21-hacs-integration-design.md`).
6. ~~Lovelace dashboard~~ — `ha_config/dashboard.yaml`, tabbed
   (raw feed / lowest price / new deals / categories), all `markdown`
   cards templated from sensor attributes, no custom cards.

## Open questions / next steps
- [x] ~~Set up the cron schedule~~ — no longer applicable: the HACS
      integration polls via each `DataUpdateCoordinator`'s own update
      interval, so there's no external scheduler to install.
- [ ] 99 Ranch's config flow collects a numeric `location_id` per config
      entry, but there's no zip→location-ID resolution — the user has to
      know/find the numeric ID themselves. That lookup remains future work.
- [ ] Zupan's `category` is always empty (page doesn't separate items by
      department) — the Category tab will only ever show H Mart items
      meaningfully grouped until/unless that's improved.
- [x] ~~`latest.json` needs to land somewhere HA can read it~~ — no longer
      applicable: the integration's coordinators read/write straight into
      HA's own state, so there's no intermediate file to hand off.
