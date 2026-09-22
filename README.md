# Grocery Ads

A personal-use Home Assistant custom integration that tracks weekly grocery
ads across eleven regional stores:

- H Mart
- Zupan's Markets
- 99 Ranch Market
- Uwajimaya
- New Seasons Market
- Market of Choice
- Asian Family Market (Beaverton, OR)
- Albertsons
- Safeway
- Fred Meyer
- Grocery Outlet

Each store gets its own `DataUpdateCoordinator`, added as a separate config
entry. H Mart, Zupan's, Albertsons, Safeway, Fred Meyer, and Grocery Outlet
expose real structured item data (name, price, sale type), and feed
cross-store **lowest price** and **new/changed deals this week** sensors —
the last four via a third-party aggregator (Flipp) that licenses their
weekly-ad data, since none of those four chains publish it through their
own site directly (see `CLAUDE.md` for details). 99 Ranch, Uwajimaya, New
Seasons Market, Market of Choice, and Asian Family Market don't publish
item-level data — they publish a weekly flyer (image or PDF) — so those
connectors just expose the current flyer URL(s) directly rather than
attempting extraction. PDF flyers embed inline on the dashboard via a small
redirect view the integration registers
(`custom_components/grocery_ads/http.py`).

Whole Foods, World Foods (Barbur/Portland), and Natural Grocers were
evaluated as additions and turned out not to be feasible (Amazon-account
gating, no weekly-ad page, and active bot-blocking, respectively) — see
`CLAUDE.md` for details.

This is a personal project, not a general-purpose HACS listing — no
translations, no brands submission, no multi-user hardening.

## Installation

1. Add this repository to HACS as a custom repository (category:
   Integration).
2. Install "Grocery Ads" from HACS and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for
   "Grocery Ads", and add one config entry per store you want to track.
   99 Ranch's config flow asks for a numeric location ID (see the open
   questions in `CLAUDE.md` — there's no zip-code lookup yet, so you'll
   need to find the ID yourself). Asian Family Market's config flow asks
   for a location code the same way — enter `OR` for Beaverton, or
   `Bellevue`, `Seattle`, or `Tukwila` for the others. Albertsons, Safeway,
   Fred Meyer, and Grocery Outlet each ask for a postal code the same
   way — enter your own zip to get the ad for your nearest store.

## More detail

For the full design rationale (why this moved from a cron script to a HACS
integration, the two connector shapes, per-store research notes, etc.), see
[`docs/plans/2026-09-21-hacs-integration-design.md`](docs/plans/2026-09-21-hacs-integration-design.md)
and `CLAUDE.md` at the repo root.
