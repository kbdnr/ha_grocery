# Grocery Ads

A personal-use Home Assistant custom integration that tracks weekly grocery
ads across twelve regional stores, and can rank your Mealie recipes by
what's on sale:

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
- Costco

Each store gets its own `DataUpdateCoordinator`, added as a separate config
entry. H Mart, Zupan's, Albertsons, Safeway, Fred Meyer, Grocery Outlet,
Costco, and Uwajimaya expose real structured item data (name, price, sale
type), and feed cross-store **lowest price** and **new/changed deals this
week** sensors — the last six via a third-party aggregator (Flipp) that
licenses their weekly-ad data, since none of those chains publish it through
their own site directly (see `CLAUDE.md` for details). 99 Ranch, New Seasons
Market, Market of Choice, and Asian Family Market don't publish item-level
data — they publish a weekly flyer (image or PDF) — so those connectors just
expose the current flyer URL(s) directly rather than attempting extraction.
Uwajimaya is both: items from Flipp, plus the PDF flyer from its own site.
PDF flyers embed inline on the dashboard via a small proxy view the
integration registers (`custom_components/grocery_ads/http.py`).

Whole Foods, World Foods (Barbur/Portland), and Natural Grocers were
evaluated as additions and turned out not to be feasible (Amazon-account
gating, no weekly-ad page, and active bot-blocking, respectively) — see
`CLAUDE.md` for details.

This is a personal project, not a general-purpose HACS listing — English
only, no brands submission, no multi-user hardening.

## Installation

1. Add this repository to HACS as a custom repository (category:
   Integration).
2. Install "Grocery Ads" from HACS and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for
   "Grocery Ads", and add one config entry per store you want to track.

What the setup dialog asks depends on the store:

| Store | Asks for | Notes |
| --- | --- | --- |
| H Mart, Zupan's, Uwajimaya, New Seasons, Market of Choice | nothing | One ad for the whole chain. (Uwajimaya's items are read for the Beaverton ZIP, 97005.) |
| Albertsons, Safeway, Fred Meyer, Grocery Outlet, Costco | ZIP code | 5-digit US ZIP; you get the ad for the nearest store. The ZIP is checked when you submit — one with no current ad for that chain is refused rather than set up empty. |
| 99 Ranch Market | store, from a dropdown | The list of all stores is read from 99ranch.com. If that fails, the dialog asks for the store number instead: the last part of the store's weekly-ad page address (`99ranch.com/stores/promotions/1693` is Beaverton). |
| Asian Family Market | store, from a dropdown | Beaverton, Bellevue, Seattle or Tukwila. |

To track two locations of one chain, add it twice. To change a location,
delete the entry and add it again.

## Recipes on sale (Mealie)

Add one more config entry from the same dialog, **Mealie (recipes on
sale)**, and give it your Mealie URL and an API token (Mealie → your
profile → API Tokens). It creates `sensor.recipes_on_sale`: its state is
the number of recipes with a fresh ingredient in this week's ads, and its
`recipes` attribute holds the top 25 with the matching ad item, store and
price for each ingredient (`foods` lists every matched ingredient). The
**Recipes** tab in `ha_config/dashboard.yaml` shows both.

How it works, and what it needs from Mealie:

- Ad items are matched to **Mealie foods by name and alias**, so recipes
  only show up if their ingredients are parsed into foods — an ingredient
  that's still free text can't match. Adding an alias to a food in Mealie
  (say "top round" on a beef food) is how you teach it a new ad wording.
- An ad item is a food only when the food name *ends* the item name
  ("Boneless Skinless Chicken Breast Fillets" is chicken breast; "Chicken
  Breast Nuggets" isn't), and recipes are ranked by how rare their on-sale
  ingredients are, so butter and eggs don't crowd out the week's specials.
- A recipe needs at least one on-sale food whose Mealie label is a fresh
  category (meat, poultry, fish, produce, dairy, cheese — the names in
  `FRESH_LABELS` in `matching.py`, which are Mealie's default labels).
- Mealie's recipe list doesn't include ingredients, so the **first sync
  reads every recipe once** — about 19 minutes for ~4,900 recipes when
  measured (four at a time, roughly a quarter second each). It runs in the
  background (the sensor is `unknown` until it finishes) and is cached in
  `<config>/grocery_ads/mealie_recipes.json`, so a restart part-way
  resumes; after that only new or edited recipes are re-read, every 6
  hours.
- It only ever reads from Mealie.

## More detail

For the full design rationale (why this moved from a cron script to a HACS
integration, the two connector shapes, per-store research notes, etc.), see
[`docs/plans/2026-09-21-hacs-integration-design.md`](docs/plans/2026-09-21-hacs-integration-design.md)
and `CLAUDE.md` at the repo root.
