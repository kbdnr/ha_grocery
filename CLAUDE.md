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
- Market of Choice
- Asian Family Market (Beaverton, OR)
- Albertsons
- Safeway
- Fred Meyer
- Grocery Outlet

Open to adding more stores later, but the pipeline should be built so adding a
new store means writing one new "connector" module, not touching the rest of
the system.

**Investigated and rejected (2026-09-21):** Whole Foods, World Foods
(Barbur/Portland), and Natural Grocers were all evaluated as candidates and
turned out not to be feasible — see their entries under "Per-store research
findings" below for why. Not stored in `STORE_REGISTRY`.

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
`DataUpdateCoordinator` on HA's own update loop; the structured stores
(H Mart, Zupan's, Albertsons, Safeway, Fred Meyer, Grocery Outlet) also
feed a shared `AggregateCoordinator` that computes the lowest-price and
new-deals views. See `docs/plans/2026-09-21-hacs-integration-design.md`
for the full design (entity/device layout, coordinator lifecycle, config
flow) rather than duplicating it here.

```
custom_components/grocery_ads/
  connectors/            # same per-store modules as before, unchanged logic
    hmart.py                # VTEX JSON API -> AdItem (structured)
    zupans.py                # WordPress REST API (HTML fragment) -> AdItem (structured)
    ranch99.py                 # scrapes __NEXT_DATA__ for flyer image URLs -> FlyerRef
    uwajimaya.py                 # scrapes weekly-specials page for PDF URL -> FlyerRef
    new_seasons.py                # scrapes /weekly-ad page for PDF URL -> FlyerRef
    market_of_choice.py             # follows a stable redirect to the current PDF -> FlyerRef
    asian_family_market.py    # base44 platform JSON entity API -> FlyerRef (per-store)
    albertsons.py               # Flipp generic aggregator API -> AdItem (structured, per-zip)
    safeway.py                     # same Flipp API, different merchant -> AdItem (structured, per-zip)
    fred_meyer.py                     # same Flipp API (site itself is bot-blocked) -> AdItem (structured, per-zip)
    grocery_outlet.py                    # same Flipp API -> AdItem (structured, per-zip)
    flipp.py                                # shared helper: postal_code -> current flyer -> AdItems, used by the four above
    base.py                        # BaseConnector (AdItem) + FlyerConnector (FlyerRef) interfaces
  const.py                # DOMAIN, STORE_REGISTRY (store metadata + kind)
  config_flow.py            # UI setup: pick a store per config entry, dup-entry guard
  coordinator.py              # GroceryAdsCoordinator + AggregateCoordinator
  sensor.py                     # GroceryAdsStoreSensor + the two aggregate sensors
  http.py                         # stable per-store redirect view for embedding PDF flyers
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

**Two connector shapes, decided 2026-09-21:** several of these stores don't
expose per-item text data on their own site — they just publish a flyer as
a PDF or a set of flipbook images with no embedded item data. Rather than
building OCR/LLM-vision extraction for those, `FlyerConnector` connectors
just locate the current flyer URL(s) and the dashboard displays it
directly (inline image, or a link to the PDF). Stores with genuine
structured data go through `BaseConnector` and produce real `AdItem`s —
those are the only ones that participate in the Lowest Price / New Deals /
Category tabs: H Mart (own VTEX API) and Zupan's (own WordPress REST API)
source this from the store's own site backend; Albertsons, Safeway, Fred
Meyer, and Grocery Outlet (added 2026-09-21) source it from a shared
third-party dependency instead — see `connectors/flipp.py` and the
per-store findings below.

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

### Market of Choice — CONFIRMED, flyer (`FlyerConnector`)
- The weekly-specials page (`marketofchoice.com/specials/weekly/`) embeds
  the ad as an Issuu flipbook (image-based, JS-rendered) with a
  screen-reader accessibility table that has price/quantity columns but no
  item-name column — not usable for structured extraction.
- Unlike Uwajimaya/New Seasons, there's a stable redirect endpoint:
  `GET https://marketofchoice.com/download-weekly-specials` 301s straight
  to the current dated PDF (`.../<YYYY-MM-DD>-MoC-Weekly-Specials.pdf`).
  The connector just follows that redirect each run — no HTML scraping or
  regex-over-page-source needed, unlike the other two PDF connectors.
- No Cloudflare/bot-blocking observed.
- `custom_components/grocery_ads/connectors/market_of_choice.py`.

### Asian Family Market — CONFIRMED, flyer (`FlyerConnector`)
- The site (`asianfamilymkt.com`) is a JS-rendered SPA built on the "base44"
  app-builder platform, backed by Supabase media storage. No item-level data,
  but the homepage's weekly-ad section is backed by a public JSON entity API
  with no auth and no Cloudflare/bot-blocking observed:
  `GET https://asianfamilymkt.com/api/apps/699266c8c2f2e91c54efa8af/entities/HomepageWeeklyAd?q={"status":"published","store":"<code>"}`
  returns per-store records with `start_date`/`end_date` and a `posters` list
  of `{display_order, image_url}` — the weekly flyer as a set of poster
  images, same shape as 99 Ranch's connector.
- Ads differ per physical store, selected via the `store` filter. Confirmed
  against the API's own `StoreQuickLink` entity (lists Bellevue, Seattle,
  Tukwila, Beaverton): the Beaverton (Oregon) location's ad is filed under
  the code `"OR"`, not `"Beaverton"` — the other three use their plain city
  names. `DEFAULT_LOCATION_ID = "OR"` since that's the store in scope; other
  locations work by passing their code as `location_id`, same
  `needs_location` pattern as 99 Ranch (`STORE_REGISTRY["asian_family_market"]["needs_location"]`
  is `True`).
- There's also a separate, seemingly-abandoned `WeeklyAd` entity
  (singular, no `store` field, one stale record from February) — not used;
  `HomepageWeeklyAd` is the live per-store data actually rendered on the
  site.
- `custom_components/grocery_ads/connectors/asian_family_market.py`.

### Albertsons, Safeway, Fred Meyer, Grocery Outlet — CONFIRMED, structured (`BaseConnector`, via shared `connectors/flipp.py`) (2026-09-21)
- All four turned out to license their weekly-ad data to the same
  third-party flyer aggregator, **Flipp** (flipp.com / Wishabi), rather
  than publishing it through their own site backends the way H Mart and
  Zupan's do. Flipp exposes two different API surfaces, and the choice of
  which one matters:
  - A **merchant-scoped widget API** (`api.flipp.com/flyerkit`,
    `dam.flippenterprise.net`) that each store's own site embeds
    client-side, keyed by a per-merchant access token shipped in that
    site's JS/HTML (not a user secret). It only returns flyer metadata and
    a PDF URL — no item text.
  - A **generic aggregator backend**, `backflipp.wishabi.com`, that
    Flipp's own consumer site/app uses. `GET
    https://backflipp.wishabi.com/flipp/flyers?locale=en-us&postal_code=<zip>`
    lists every currently-active flyer for that zip across every retailer
    Flipp covers (dozens, including Fred Meyer, QFC, Albertsons, Safeway,
    Grocery Outlet, Walmart, Home Depot, even Uwajimaya). `GET
    .../flipp/flyers/<flyer_id>?locale=en-us&postal_code=<zip>` then
    returns that flyer's full item list — confirmed real per-item `name`,
    `price`, `brand`, and `discount` fields (no `unit` field) for all four
    of these stores. Both endpoints are public and unauthenticated (just a
    postal code, no token, no login), with no Cloudflare/bot-blocking
    observed.
  - This generic endpoint is what these four connectors use — it's
    genuinely structured per-item data, not a nice-to-have extraction
    pipeline, so it goes through `BaseConnector` rather than
    `FlyerConnector` despite these stores otherwise looking like flyer-only
    candidates.
- A merchant sometimes has more than one flyer active at once (e.g.
  Albertsons' "Big Book of Savings" insert runs for weeks alongside the
  actual "Weekly Ad"); `connectors/flipp.py` picks whichever currently-valid
  flyer for that merchant has the shortest date range, on the assumption
  that's the real weekly ad.
- `fredmeyer.com`/`kroger.com` themselves are unreachable to non-browser
  clients at all — `curl` gets an immediate HTTP/2 stream reset, and
  HTTP/1.1 hangs to a timeout. This is connection-level (Akamai-style) bot
  management, more aggressive than Natural Grocers' simple 403 page. Fred
  Meyer's data is only reachable through Flipp's aggregator, not the
  store's own site at all — worth remembering since a future first-party
  fredmeyer.com connector isn't buildable the way the other stores' are.
- `category` and `unit` are always empty for these four (the endpoint
  doesn't provide them) — same gap as Zupan's `category`. `sale_type` is
  synthesized as `"<discount>% off"` when Flipp provides a discount
  percentage, else `"sale"`.
- Needs a postal code per config entry (`needs_location: True`, same
  pattern as 99 Ranch/Asian Family Market); `DEFAULT_LOCATION_ID = "97005"`
  (Beaverton, OR) on all four, like Asian Family Market's OR default.
- Depending on a third-party aggregator rather than each store's own
  backend is a bigger risk surface than H Mart/Zupan's (Flipp could change
  its API, rate-limit, or drop a merchant), but it's the only public,
  unauthenticated source of item-level data for any of these four chains.
- `custom_components/grocery_ads/connectors/flipp.py` (shared),
  `albertsons.py`, `safeway.py`, `fred_meyer.py`, `grocery_outlet.py`.

### Whole Foods Market — REJECTED, no public data (2026-09-21)
- `wholefoodsmarket.com/sales-flyer` is a JS-rendered shell with no
  `__NEXT_DATA__`/embedded item data in the initial HTML payload, and
  explicitly gates on an authenticated Amazon account + store selection —
  weekly deals live behind the Amazon-integrated pricing system, not a
  public endpoint.
- No PDF/flipbook flyer fallback either — Whole Foods has no print-style
  weekly ad anymore. Not buildable as either connector shape without an
  authenticated Amazon session, which is out of scope.

### World Foods Market (Barbur/Portland) — REJECTED, no weekly-ad presence (2026-09-21)
- The old Barbur-specific site (`barburworldfoods.com/specials.asp`) has
  been retired and 301s to the combined current site,
  `worldfoodsportland.com`, a 6-page Squarespace brochure site (confirmed
  via `sitemap.xml`) with no weekly-ad, specials, or flyer page at all.
- A third-party ad aggregator lists "weekly specials" for this store, but
  there's no first-party page, PDF, or API to source them from — not
  buildable.

### Natural Grocers — REJECTED, blocked by WAF (2026-09-21)
- `naturalgrocers.com/sale-flyers/` (redirects to `/hot-deals`) and
  `/deals-limited-time-only` both return a branded "Access denied" 403 —
  this is Drupal + Cloudflare with an active bot-blocking rule on these
  specific pages, not a simple missing-User-Agent issue: the exact
  `BROWSER_HEADERS` set that gets past Uwajimaya's/New Seasons'/Zupan's
  Cloudflare checks is blocked here too.
- Did not attempt further evasion (browser fingerprinting workarounds,
  headless-browser challenge solving) — that crosses from "look like a
  normal browser request" into deliberately defeating bot protection,
  which is out of scope for this project.

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
   cards templated from sensor attributes, plus native `iframe` cards
   (backed by `http.py`'s redirect view) for embedding PDF flyers inline.
7. ~~`connectors/market_of_choice.py`~~ — done (flyer connector, stable
   redirect endpoint). Whole Foods, World Foods, and Natural Grocers were
   investigated and rejected — see per-store findings above.
8. ~~`connectors/asian_family_market.py`~~ — done (flyer connector, public
   base44 JSON entity API, `needs_location` per-store like 99 Ranch;
   defaults to the Beaverton, OR location).
9. ~~`connectors/albertsons.py`, `connectors/safeway.py`,
   `connectors/fred_meyer.py`, `connectors/grocery_outlet.py`~~ — done, all
   four structured (`BaseConnector`) via a shared `connectors/flipp.py`
   helper around Flipp's generic aggregator backend — see per-store
   findings above. Needs a per-entry postal code (`needs_location`, default
   `97005`/Beaverton OR) like 99 Ranch/Asian Family Market.

## Open questions / next steps
- [x] ~~Set up the cron schedule~~ — no longer applicable: the HACS
      integration polls via each `DataUpdateCoordinator`'s own update
      interval, so there's no external scheduler to install.
- [ ] 99 Ranch's config flow collects a numeric `location_id` per config
      entry, but there's no zip→location-ID resolution — the user has to
      know/find the numeric ID themselves. That lookup remains future work.
- [ ] Zupan's, Albertsons', Safeway's, Fred Meyer's, and Grocery Outlet's
      `category` is always empty (none of those sources separate items by
      department) — the Category tab will only ever show H Mart items
      meaningfully grouped until/unless that's improved. The latter four
      are also missing `unit` (Flipp's item data doesn't include it).
- [x] ~~`latest.json` needs to land somewhere HA can read it~~ — no longer
      applicable: the integration's coordinators read/write straight into
      HA's own state, so there's no intermediate file to hand off.
- [ ] Albertsons/Safeway/Fred Meyer/Grocery Outlet all depend on Flipp's
      third-party aggregator backend (`backflipp.wishabi.com`) rather than
      each store's own site — a bigger single point of failure than H
      Mart/Zupan's two independent backends. Not addressed; noted as a risk
      in the per-store findings above.
- [ ] Like 99 Ranch, the postal code for these four stores is a manually
      entered config-flow value (`DEFAULT_LOCATION_ID = "97005"`, no
      zip-code lookup/validation) — same future work as 99 Ranch's
      location ID.
