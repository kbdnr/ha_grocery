# Grocery Ads

A personal-use Home Assistant custom integration that tracks weekly grocery
ads across five regional stores:

- H Mart
- Zupan's Markets
- 99 Ranch Market
- Uwajimaya
- New Seasons Market

Each store gets its own `DataUpdateCoordinator`, added as a separate config
entry. H Mart and Zupan's expose real structured item data (name, price,
unit, sale type), and feed cross-store **lowest price** and **new/changed
deals this week** sensors. 99 Ranch, Uwajimaya, and New Seasons Market don't
publish item-level data — they publish a weekly flyer (image or PDF) — so
those three connectors just expose the current flyer URL(s) directly rather
than attempting extraction.

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
   need to find the ID yourself).

## More detail

For the full design rationale (why this moved from a cron script to a HACS
integration, the two connector shapes, per-store research notes, etc.), see
[`docs/plans/2026-09-21-hacs-integration-design.md`](docs/plans/2026-09-21-hacs-integration-design.md)
and `CLAUDE.md` at the repo root.
