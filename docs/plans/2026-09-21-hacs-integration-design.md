# Grocery Ads HACS Integration — Design Doc
**Date:** 2026-09-21
**Status:** Approved

## Goal

Convert the standalone cron-scheduled scraper (`run.py` + `command_line` sensors
reading `latest.json`) into a personal-use HACS custom integration
(`custom_components/grocery_ads/`). This was anticipated from the start — see
"Long-term target" in `2026-08-29-grocery-tracker-design.md` — and is being done
now because the next phase of work (zip-code-based store lookup, adding more
chains generically) will be materially harder to retrofit onto the
file-based/cron design than to build integration-native from here.

Scope: personal use only. Not targeting HACS default-repo listing, HA brands
submission, or core inclusion — so no translations, no strict hassfest/HACS
validation bar, no multi-user config-flow hardening. Just a real HACS custom
repository installed on one instance.

## Why now, and what it fixes

The current design's weakest point, flagged in the prior CLAUDE.md open
questions, is that `latest.json` has to be filesystem-visible to the HA
process — a bind mount or symlink if HA runs in a container. Running the
scraper *inside* HA as a proper integration removes that problem entirely:
the integration writes its SQLite db under HA's own config directory, so
there's nothing to mount.

It also replaces cron (never actually installed anywhere persistent) with
HA's own `DataUpdateCoordinator` scheduling, and replaces the hardcoded
`CONNECTORS`/`FLYER_CONNECTORS` lists in `run.py` with a config-flow-driven
registry — which is what makes "add a store via zip code" and "generic store
selection" tractable as UI-driven features instead of code edits to a list.

## Chosen approach

Keep the existing library (`connectors/`, `schema.py`, `db.py`) almost
untouched — it has zero HA dependencies today and stays that way. Wrap it in
a thin integration layer: config flow, coordinators, sensors. The sync
`requests`/`bs4` connector code is unchanged; it just runs inside
`hass.async_add_executor_job` instead of a bare Python process.

## Project structure

```
custom_components/grocery_ads/
  __init__.py           # async_setup / async_setup_entry / async_unload_entry
  manifest.json          # domain "grocery_ads", requirements: requests, beautifulsoup4
  config_flow.py         # store-type dropdown (from STORE_REGISTRY) -> per-store setup schema
  coordinator.py         # GroceryAdsCoordinator; aggregate coordinator for cross-store data
  sensor.py              # per-entry sensors + the two aggregate sensors
  const.py               # DOMAIN, STORE_REGISTRY: store_id -> (name, connector cls, setup schema)
  connectors/             # hmart.py, ranch99.py, uwajimaya.py, zupans.py, new_seasons.py — unchanged
  schema.py               # AdItem / FlyerRef — unchanged
  db.py                   # unchanged logic; path now hass.config.path("grocery_ads", "groceries.db")

run.py                   # kept as a dev CLI for exercising connectors outside HA (--dry-run/--stores)
requirements.txt          # kept for the dev-CLI path only; HA installs its own copy via manifest.json
docs/plans/
```

`ha_config/sensors.yaml` (the `command_line` sensors) is removed from the
production path once the integration is installed. `ha_config/dashboard.yaml`
is kept and hand-edited as store entries are added/removed (decided
explicitly — no auto-templating).

## Config flow

One `ConfigEntry` per store *instance*, not one entry covering all stores:

1. User picks a store type from a dropdown sourced from `STORE_REGISTRY` —
   the same registry is what "adding a new store" means going forward:
   one new registry entry + one new connector module, same principle as
   today's "one connector module, not touching the rest of the system,"
   just exposed through HA's UI instead of a Python list edit.
2. If the store type needs location info (99 Ranch's zip → store ID), a
   second step collects it. Stores with a single static endpoint (H Mart,
   Zupan's, Uwajimaya, New Seasons today) skip straight to creation.
3. Each submission creates its own entry/coordinator/entities, so the same
   chain can be added twice for two physical locations.

## Data flow & entities

**Per-entry coordinator:** `GroceryAdsCoordinator(DataUpdateCoordinator)`,
one per config entry, calls its connector's `fetch()` via
`hass.async_add_executor_job`. Default `update_interval` ~6h (covers the
Wed/Thu ad-rotation window; not pinned to exact cron times).

**Cross-store aggregation (lowest price / new-deals diff):** this doesn't
map onto "one coordinator per entry" since it's inherently cross-store.
Kept as-is: `db.py`'s SQLite logic (`insert_items()`, `compute_diff()`)
is reused unchanged. Every structured-store coordinator (H Mart, Zupan's)
writes its fetched `AdItem`s into one shared `groceries.db` after each
fetch. A second, always-present aggregate coordinator — spun up once in
`async_setup`, not tied to a user-created config entry — periodically
reads the db and refreshes two aggregate sensors.

**Entities:**
- Structured store entry (H Mart, Zupan's): `sensor.grocery_ads_<store>`,
  state = item count, `items` attribute = list of `AdItem` dicts (same
  shape `latest.json` used today).
- Flyer store entry (99 Ranch, Uwajimaya, New Seasons):
  `sensor.grocery_ads_<store>`, state = `valid_to` date, attributes =
  `urls`/`media_type`.
- Aggregate (not tied to any one store entry):
  `sensor.grocery_ads_lowest_price` (attribute = lowest-price dict) and
  `sensor.grocery_ads_new_deals` (attribute = diff dict: new/changed/dropped).

Attribute shapes intentionally match today's `latest.json` output, so the
dashboard's markdown-card templates need minimal changes.

## Storage & migration

`groceries.db` moves to `hass.config.path("grocery_ads", "groceries.db")` —
inside HA's own config directory, since the integration now runs inside the
HA process. This is what eliminates the bind-mount/symlink problem, not a
separate fix.

No data migration needed: per the prior design doc's open questions, the
cron schedule was never installed anywhere persistent, so there's no
production history in the current `groceries.db`/`latest.json` to carry
over. First load creates a fresh db.

## Testing

`schema.py`, connector tests, and (for the dev-CLI path) `writer.py`/`run.py`
tests are untouched — none of them know about HA. New tests needed:
- `config_flow.py`: store selection step + per-store setup step (e.g. 99
  Ranch's zip/location step), using `pytest-homeassistant-custom-component`.
- `coordinator.py`: executor wrapping and per-coordinator error isolation
  (mirrors the try/except-per-connector behavior `run.py` already has and is
  tested for).
- Aggregate coordinator: db-write-then-aggregate-read round trip.

## Manifest

```json
{
  "domain": "grocery_ads",
  "requirements": ["requests>=2.31.0", "beautifulsoup4>=4.12.0"]
}
```
HA installs these automatically on integration load. `requirements.txt` stays
for the dev-CLI (`run.py`) path only.

## What's explicitly out of scope

- HACS default-repo listing / HA brands / core submission.
- Translations.
- Auto-templated dashboard (decided: hand-edit `dashboard.yaml` as stores are
  added).
- Freeform/arbitrary-URL store scraping — store selection stays a dropdown
  of chains with a written connector, matching the existing one-module-per-
  store philosophy.
