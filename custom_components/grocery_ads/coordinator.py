from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STORE_KIND_FLYER, STORE_KIND_ITEMS
from .db import Database
from .matching import FoodIndex, find_offers, rank_recipes
from .mealie import load_cache, sync_recipes

_LOGGER = logging.getLogger(__name__)
DEFAULT_UPDATE_INTERVAL = timedelta(hours=6)
RECIPE_LIMIT = 25


class GroceryAdsCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        connector,
        kind: str,
        db_path: str | Path,
        entry_id: str,
        flyer_connector=None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{connector.store_id}_{entry_id}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.connector = connector
        self.kind = kind
        self.db_path = db_path
        # An items store can also have a flyer to show (Uwajimaya: items
        # from Flipp, PDF from its own site), fetched by a second connector.
        self.flyer_connector = flyer_connector
        # The store's current FlyerRef, whichever connector it came from --
        # for a flyer-kind store it's the same object as `data`.
        self.flyer = None

    async def _async_update_data(self):
        flyer_failed = False
        if self.flyer_connector is not None:
            try:
                self.flyer = await self.hass.async_add_executor_job(self.flyer_connector.fetch)
            except Exception as err:
                flyer_failed = True
                _LOGGER.warning("%s: fetching the flyer failed: %s", self.connector.store_id, err)

        try:
            result = await self.hass.async_add_executor_job(self.connector.fetch)
        except Exception as err:
            if self.flyer_connector is None or flyer_failed:
                raise UpdateFailed(f"{self.connector.store_id}: {err}") from err
            # The two sources are independent, so one of them being down
            # shouldn't take the other off the dashboard.
            _LOGGER.warning("%s: fetching items failed: %s", self.connector.store_id, err)
            return self.data or []

        if self.kind == STORE_KIND_FLYER:
            self.flyer = result
        if self.kind == STORE_KIND_ITEMS and result:
            await self.hass.async_add_executor_job(self._persist, result)
        return result

    def _persist(self, items) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Database(self.db_path).insert_items(items)


class AggregateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, db_path: str | Path, config_entry=None):
        # config_entry is explicitly passed through (default None) rather than
        # left unset: DataUpdateCoordinator.__init__ treats an *unset*
        # config_entry as a signal to auto-bind self.config_entry from HA's
        # `current_entry` ContextVar, i.e. whichever config entry's
        # async_setup_entry happens to be executing at construction time.
        # That entry has no logical relationship to aggregate ownership
        # (AGGREGATE_OWNER_KEY, tracked separately in sensor.py), so relying
        # on the auto-bind ties this coordinator's async_on_unload-driven
        # shutdown to an unrelated entry's lifecycle. Passing None explicitly
        # suppresses the auto-bind, leaves self.config_entry as None, and
        # this coordinator's shutdown is handled explicitly in
        # __init__.py's async_unload_entry instead.
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_aggregate",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.db_path = db_path

    async def _async_update_data(self):
        return await self.hass.async_add_executor_job(self._read)

    def _read(self) -> dict:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        db = Database(self.db_path)
        return {
            "diff": db.compute_diff(),
            "lowest_price": self._lowest_price(db.get_latest_items()),
        }

    @staticmethod
    def _lowest_price(items) -> dict:
        lowest: dict = {}
        for item in items:
            if item.item_name not in lowest or item.price < lowest[item.item_name]["price"]:
                lowest[item.item_name] = {"store": item.store, "price": item.price}
        return lowest


class RecipeCoordinator(DataUpdateCoordinator):
    """Recipes from Mealie whose ingredients are in this week's ads.

    A refresh re-reads Mealie (foods, plus any recipes that changed); the
    matching itself is cheap and is redone whenever a store's ads update,
    via async_recompute().
    """

    def __init__(self, hass: HomeAssistant, client, cache_path: str | Path, config_entry):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_recipes",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.cache_path = cache_path
        self._index: FoodIndex | None = None
        self._recipes: dict[str, dict] = {}
        self._group_slug = ""

    async def _async_update_data(self):
        try:
            await self.hass.async_add_executor_job(self._sync)
        except Exception as err:
            raise UpdateFailed(f"mealie: {err}") from err
        return self._overlay()

    def _sync(self) -> None:
        self._group_slug = self.client.group_slug()
        index = FoodIndex(self.client.foods())
        cache = self._recipes or load_cache(self.cache_path)
        self._recipes = sync_recipes(self.client, cache, self.cache_path)
        self._index = index

    @callback
    def async_recompute(self) -> None:
        """Re-match against the stores' current ads without touching Mealie."""
        if self._index is None:
            return
        self.data = self._overlay()
        self.async_update_listeners()

    def _overlay(self) -> dict:
        offers = find_offers(self._current_items(), self._index)
        ranked = rank_recipes(self._recipes, offers, self._index)
        recipes = ranked[:RECIPE_LIMIT]
        for recipe in recipes:
            recipe["url"] = self.client.recipe_url(self._group_slug, recipe["slug"])
        return {
            "count": len(ranked),
            "recipes": recipes,
            "foods": {
                self._index.names[food_id]: food_offers[0]
                for food_id, food_offers in sorted(
                    offers.items(), key=lambda pair: self._index.names[pair[0]].lower()
                )
            },
            "recipes_indexed": len(self._recipes),
            "recipes_with_foods": sum(1 for recipe in self._recipes.values() if recipe["foods"]),
        }

    def _current_items(self) -> list:
        items = []
        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            store = entry_data["coordinator"]
            if store.kind == STORE_KIND_ITEMS and store.data:
                items.extend(store.data)
        return items
