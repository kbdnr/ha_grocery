from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STORE_KIND_ITEMS
from .db import Database

_LOGGER = logging.getLogger(__name__)
DEFAULT_UPDATE_INTERVAL = timedelta(hours=6)


class GroceryAdsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, connector, kind: str, db_path: str | Path, entry_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{connector.store_id}_{entry_id}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.connector = connector
        self.kind = kind
        self.db_path = db_path

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(self.connector.fetch)
        except Exception as err:
            raise UpdateFailed(f"{self.connector.store_id}: {err}") from err

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
