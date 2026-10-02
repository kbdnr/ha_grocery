"""Read-only Mealie client: the food vocabulary, and which foods each
recipe uses.

Mealie's recipe list doesn't include ingredients, so finding out which
foods a recipe uses takes one request per recipe. That's thousands of
requests for a big library, so the result is kept in a cache file and a
recipe is only re-fetched when its `updatedAt` changes.
"""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 60  # seconds
PAGE_SIZE = 500
SAVE_EVERY = 250  # recipes fetched between cache writes during a long first sync
# A recipe takes a few tenths of a second to fetch, so a first sync of
# thousands is half an hour one at a time. A handful at once is still a
# light load for Mealie.
WORKERS = 4


class MealieClient:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, **params) -> dict:
        resp = self._session.get(f"{self.url}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _get_all(self, path: str) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            data = self._get(path, page=page, perPage=PAGE_SIZE)
            items.extend(data["items"])
            if page >= (data.get("total_pages") or 1):
                return items
            page += 1

    def group_slug(self) -> str:
        """The token owner's group, which is part of every recipe's web URL.
        Doubles as the connection/credentials check."""
        return self._get("/api/users/self")["groupSlug"]

    def foods(self) -> list[dict]:
        return self._get_all("/api/foods")

    def recipe_summaries(self) -> list[dict]:
        return self._get_all("/api/recipes")

    def recipe_food_ids(self, slug: str) -> list[str]:
        recipe = self._get(f"/api/recipes/{slug}")
        food_ids = []
        for ingredient in recipe.get("recipeIngredient") or []:
            food_id = (ingredient.get("food") or {}).get("id")
            if food_id and food_id not in food_ids:
                food_ids.append(food_id)
        return food_ids

    def recipe_url(self, group_slug: str, slug: str) -> str:
        return f"{self.url}/g/{group_slug}/r/{slug}"


def load_cache(path: str | Path) -> dict[str, dict]:
    try:
        return json.loads(Path(path).read_text())["recipes"]
    except (OSError, ValueError, KeyError):
        return {}


def save_cache(path: str | Path, recipes: dict[str, dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"recipes": recipes}))
    os.replace(tmp, path)


def sync_recipes(client: MealieClient, cache: dict[str, dict], cache_path: str | Path) -> dict[str, dict]:
    """Brings `cache` (slug -> {"name", "updated", "foods"}) in line with
    Mealie and returns it: fetches recipes that are new or changed, drops
    ones that are gone. A recipe that fails to fetch is left as it was and
    picked up again next time."""
    summaries = client.recipe_summaries()
    recipes = {}
    stale = {}
    for summary in summaries:
        slug = summary["slug"]
        updated = summary.get("updatedAt") or summary.get("dateUpdated")
        cached = cache.get(slug)
        if cached and cached.get("updated") == updated:
            recipes[slug] = cached
        else:
            stale[slug] = {"name": summary.get("name") or slug, "updated": updated}

    fetched = failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(client.recipe_food_ids, slug): slug for slug in stale}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                food_ids = future.result()
            except requests.RequestException as err:
                _LOGGER.debug("Fetching Mealie recipe %s failed: %s", slug, err)
                failed += 1
                if slug in cache:
                    recipes[slug] = cache[slug]
                continue
            recipes[slug] = {**stale[slug], "foods": food_ids}
            fetched += 1
            if fetched % SAVE_EVERY == 0:
                # Recipes not reached yet keep their old cache entry, so a
                # restart mid-sync resumes instead of starting over.
                save_cache(cache_path, {**cache, **recipes})

    if failed:
        _LOGGER.warning("%d Mealie recipe(s) could not be fetched; will retry next sync", failed)
    if fetched or len(recipes) != len(cache):
        save_cache(cache_path, recipes)
    return recipes
