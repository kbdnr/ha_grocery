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
- Costco

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
5. **Recipes on sale** — Mealie recipes ranked by which of their
   ingredients are in this week's ads (added 2026-10-01, see "Recipe
   overlay" below)

## Architecture

The project ships as a Home Assistant HACS custom integration —
`custom_components/grocery_ads/` — installed via Settings -> Devices &
Services -> Add Integration, one config entry per store, rather than a
standalone script run from cron. Each store's connector runs inside a
`DataUpdateCoordinator` on HA's own update loop; the structured stores
(H Mart, Zupan's, Albertsons, Safeway, Fred Meyer, Grocery Outlet, Costco,
Uwajimaya) also feed a shared `AggregateCoordinator` that computes the lowest-price and
new-deals views. See `docs/plans/2026-09-21-hacs-integration-design.md`
for the full design (entity/device layout, coordinator lifecycle, config
flow) rather than duplicating it here.

```
custom_components/grocery_ads/
  connectors/            # same per-store modules as before, unchanged logic
    hmart.py                # VTEX JSON API -> AdItem (structured)
    zupans.py                # WordPress REST API (HTML fragment) -> AdItem (structured)
    ranch99.py                 # scrapes __NEXT_DATA__ for flyer image URLs -> FlyerRef
    uwajimaya.py                 # two connectors: weekly-specials page PDF URL -> FlyerRef, and Flipp -> AdItem
    new_seasons.py                # scrapes /weekly-ad page for PDF URL -> FlyerRef
    market_of_choice.py             # follows a stable redirect to the current PDF -> FlyerRef
    asian_family_market.py    # base44 platform JSON entity API -> FlyerRef (per-store)
    albertsons.py               # Flipp generic aggregator API -> AdItem (structured, per-zip)
    safeway.py                     # same Flipp API, different merchant -> AdItem (structured, per-zip)
    fred_meyer.py                     # same Flipp API (site itself is bot-blocked) -> AdItem (structured, per-zip)
    grocery_outlet.py                    # same Flipp API -> AdItem (structured, per-zip)
    costco.py                               # same Flipp API (its grocery coupon book) -> AdItem (structured, per-zip)
    flipp.py                                # shared helper: postal_code -> current flyer -> AdItems, used by the five above + Uwajimaya
    base.py                        # BaseConnector (AdItem) + FlyerConnector (FlyerRef) interfaces
  const.py                # DOMAIN, STORE_REGISTRY (store metadata + kind)
  config_flow.py            # UI setup: pick a store per config entry, then its ZIP / store, dup-entry guard
  translations/en.json      # every label, help text and error the config flow shows
  coordinator.py              # GroceryAdsCoordinator + AggregateCoordinator + RecipeCoordinator
  sensor.py                     # GroceryAdsStoreSensor + the two aggregate sensors + the recipes sensor
  matching.py                   # pure Python: ad item name -> Mealie food, and recipe ranking
  mealie.py                     # read-only Mealie client + cached recipe -> foods index
  http.py                         # stable per-store view that proxies flyer bytes for iframe embedding
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
- Ads differ per store, so the entry stores a numeric store ID as
  `location_id` (`needs_location: True`). The config flow offers the stores
  by name: `POST https://www.99ranch.com/be-api/store/web/view/allStores`
  with an empty JSON body (the site's own store-locator backend; public,
  no auth, GET is rejected) returns all 66 stores grouped by state, each
  with `id`, `name`, `state`, address and lat/long —
  `Ranch99Connector.list_locations()`. Beaverton is `1693`, Portland
  `1695`; the constructor default `1007` is Arcadia, CA.
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
  is `True`). The four codes are the `LOCATIONS` dict in the connector,
  shown as a dropdown in the config flow.
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

### Costco, and Uwajimaya's items — CONFIRMED, structured, via Flipp (2026-10-01)
- Both are on the same Flipp aggregator endpoint as the four stores above
  (Flipp's merchant strings are `"Costco "` and `"Uwajimaya\t"`, trailing
  whitespace included — `flipp.py` strips it before comparing).
- **Costco** runs two flyers over the same dates: "Flyer" (general
  merchandise/pharmacy/automotive) and "CP Grocery". Shortest-date-range
  alone can't tell them apart, so `_select_current_flyer` prefers a flyer
  whose `categories_csv` contains `Groceries`, then the shortest range.
  The grocery book still has non-food in it (tape, lotion); that's left in
  the raw feed and simply never matches a food. `needs_location: True`.
- **Uwajimaya** is the one store with both shapes: `UwajimayaItemsConnector`
  (Flipp, ~35 items/week) is its registry `connector`, and the original
  PDF-scraping `UwajimayaConnector` is its `flyer_connector`.
  `GroceryAdsCoordinator` runs both and keeps the FlyerRef on
  `coordinator.flyer` (for flyer-only stores that's the same object as
  `coordinator.data`), which is what `http.py` and the sensor's
  `urls`/`media_type` attributes read. One source failing doesn't take the
  other down; the update only fails if both do.
  `needs_location` stays `False` (items are read for the default 97005) so
  the config entry created when Uwajimaya was flyer-only keeps working
  without migration. Its sensor state changed from the flyer's valid_to
  date to the item count; the date is now the `flyer_valid_to` attribute.
- Flipp lists two identical Uwajimaya "Indexed Weekly" flyers; either one
  is fine.

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

## Config flow: how a location is asked for (2026-10-01)

`location_id` means three different things across stores, and the original
single free-text "location" step (with no translations file, so the field
was literally labelled `location_id`) didn't say which. Each
`needs_location` store now declares a `location_kind` in `STORE_REGISTRY`,
and the entry data shape is unchanged (`{store_type, location_id}`), so
existing entries need no migration:

- `LOCATION_POSTAL_CODE` (the five Flipp stores) -> step `postal_code`: a
  5-digit ZIP, then the connector's `fetch()` is run once; no items is the
  `no_ad_found` error instead of an entry that sits at 0. Flipp answers an
  unknown ZIP with an empty list, not an HTTP error. Costco's coupon book
  came back for every ZIP tried (even 99950, Ketchikan), so the check
  doesn't catch a wrong ZIP for it.
- `LOCATION_STORE` (99 Ranch, Asian Family Market) -> step `store`: a
  dropdown of the connector's `list_locations()` (`{location_id: label}`),
  and the label goes in the entry title ("99 Ranch Market (Beaverton,
  OR)"). If the list can't be loaded the flow drops to step
  `store_number`, the old typed-in field with an explanation.
- All wording lives in `translations/en.json`. hassfest rejects URLs in
  translation strings, so example addresses are passed as
  `description_placeholders` from `config_flow.py`.
- A new connector that needs a location sets `location_kind` and, for
  `LOCATION_STORE`, adds a `list_locations()`; no config-flow change.
- Not built: a reconfigure step (changing a location means delete and
  re-add), and sorting 99 Ranch's list by distance from HA's home.

## Recipe overlay (Mealie) — added 2026-10-01

A separate config entry type, `ENTRY_TYPE_MEALIE` (picked from the same
dropdown as the stores, stored under `CONF_STORE_TYPE` but deliberately not
in `STORE_REGISTRY`), connects a Mealie instance by URL + API token and
creates `sensor.recipes_on_sale`.

- `matching.py` is pure Python and holds all the judgement. The join key is
  Mealie's food vocabulary (name, plural, aliases). An ad item matches a
  food only when the food phrase *ends* the item name (the head noun),
  after splitting alternatives on "or"/commas. Known rules, each there
  because of a real false match in the 2026-09-30 ads: whole-item block
  words (`_NOT_INGREDIENT`: "Hand Cream", "Prebiotic Soda Orange"), pairs
  ("Mac & Cheese"), chocolate shapes ("Chocolate Pumpkins"), lone flavour
  words after a comma ("Noodle Bowl, Chicken"), and elision ("Orange or
  Carrot Juice" is orange juice). Trailing cut/packaging words
  (`_TAIL_NOISE`) are only looked past when the name doesn't match with
  them. Measured on that week: 741 priced items across 7 Flipp stores ->
  291 matched -> 123 foods (64 fresh).
- Known wrong matches that are left alone: brand-as-product ("Russell
  Stover Pumpkin" is candy; `AdItem` has no brand field to strip), wine
  named like food ("La Crema"), and ready-to-eat items ("Fresh Roasted
  Chicken"). Misses are mostly vocabulary: cuts with no Mealie food or
  alias ("Top Round Steaks", "Flanken Style Ribs") — fixed by adding the
  alias in Mealie, not here.
- Ranking: a recipe is listed if at least one on-sale food has a fresh
  label (`FRESH_LABELS`, Mealie's default label names); score is the sum
  of log(recipes / recipes using the food) over those, so staples count
  for almost nothing. Ties go to coverage of the whole ingredient list.
- `mealie.py`: `GET /api/recipes` (summaries) has no ingredients, so each
  recipe is fetched once and the food ids cached in
  `<config>/grocery_ads/mealie_recipes.json`, keyed by slug and
  re-fetched only when `updatedAt` changes. The first sync runs as a
  background task so entry setup isn't held up. Read-only: GETs only.
- `RecipeCoordinator` re-reads Mealie every 6 hours; the matching itself
  is redone (no Mealie I/O) whenever an items store's coordinator updates
  or unloads, via a listener registered in `__init__.py`. It reads ad items
  from the live store coordinators, not from SQLite.
- "On sale" means "in the ad": Flipp gives no regular price and a discount
  percentage on only ~1 in 5 items. Seasonality isn't built — it would
  come from the history `ad_items` accumulates in SQLite.

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
   (backed by `http.py`'s proxy view) for embedding PDF flyers inline.
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

10. ~~`connectors/costco.py`, Uwajimaya items alongside its PDF~~ — done
    2026-10-01, both via Flipp.
11. ~~Recipe overlay~~ — done 2026-10-01 (`matching.py`, `mealie.py`,
    `RecipeCoordinator`, `sensor.recipes_on_sale`, Recipes dashboard tab).

## Open questions / next steps
- [ ] `Database.get_latest_items()` selects `MAX(scrape_batch)` across all
      stores, but since the HACS conversion each store's coordinator
      inserts its own batch — so the Lowest Price and New Deals sensors
      only ever reflect whichever store refreshed last. Noticed 2026-10-01
      while building the recipe overlay (which avoids it by reading the
      live coordinators); not fixed.
- [ ] Recipe overlay: no seasonality yet, and `FRESH_LABELS` /
      the matcher's word lists are constants rather than configuration.
- [x] ~~Set up the cron schedule~~ — no longer applicable: the HACS
      integration polls via each `DataUpdateCoordinator`'s own update
      interval, so there's no external scheduler to install.
- [x] ~~99 Ranch's config flow needs a numeric `location_id` the user has
      to find themselves~~ — done 2026-10-01: stores are picked by name
      from a dropdown (see "Config flow" above).
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
- [x] ~~The postal code for the Flipp stores is entered with no
      validation~~ — done 2026-10-01: format-checked and tried against
      Flipp in the config flow.
