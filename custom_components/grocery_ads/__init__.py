from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    CONF_LOCATION_ID,
    CONF_STORE_TYPE,
    CONF_TOKEN,
    CONF_URL,
    DB_FILENAME,
    DOMAIN,
    ENTRY_TYPE_MEALIE,
    RECIPE_CACHE_FILENAME,
    RECIPE_COORDINATOR_KEY,
    STORE_KIND_ITEMS,
    STORE_REGISTRY,
)
from .coordinator import AggregateCoordinator, GroceryAdsCoordinator, RecipeCoordinator
from .http import GroceryAdsFlyerView
from .mealie import MealieClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {AGGREGATE_OWNER_KEY: None})
    hass.http.register_view(GroceryAdsFlyerView(hass))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {AGGREGATE_OWNER_KEY: None})
    if entry.data[CONF_STORE_TYPE] == ENTRY_TYPE_MEALIE:
        return await _async_setup_mealie_entry(hass, entry)

    db_path = Path(hass.config.path(DOMAIN, DB_FILENAME))

    entry_conf = STORE_REGISTRY[entry.data[CONF_STORE_TYPE]]
    if entry_conf["needs_location"]:
        connector = entry_conf["connector"](location_id=entry.data[CONF_LOCATION_ID])
    else:
        connector = entry_conf["connector"]()
    flyer_connector = entry_conf["flyer_connector"]() if "flyer_connector" in entry_conf else None

    coordinator = GroceryAdsCoordinator(
        hass, connector, entry_conf["kind"], db_path, entry.entry_id, flyer_connector
    )
    await coordinator.async_config_entry_first_refresh()

    if AGGREGATE_COORDINATOR_KEY not in domain_data:
        # config_entry=None decouples the aggregate coordinator's lifecycle
        # from whichever entry happens to be mid-setup right now (it would
        # otherwise auto-bind to it via HA's ContextVar and get torn down
        # permanently the first time that unrelated entry is unloaded). Its
        # lifecycle is instead managed explicitly in async_unload_entry.
        aggregate_coordinator = AggregateCoordinator(hass, db_path, config_entry=None)
        # async_config_entry_first_refresh() requires self.config_entry to be
        # set (it raises ConfigEntryError otherwise, verified against the
        # installed homeassistant.helpers.update_coordinator source) -- since
        # this coordinator deliberately has no config_entry, async_refresh()
        # is used instead. It behaves the same for our purposes (populates
        # .data, sets last_update_success) but logs rather than raising
        # ConfigEntryNotReady on failure, which is fine here: this reads the
        # local SQLite db, not a network resource.
        await aggregate_coordinator.async_refresh()
        domain_data[AGGREGATE_COORDINATOR_KEY] = aggregate_coordinator

    domain_data[entry.entry_id] = {"coordinator": coordinator}

    if entry_conf["kind"] == STORE_KIND_ITEMS:
        # The recipe overlay is matched against every store's current ads,
        # so it's redone whenever one of them changes or goes away.
        entry.async_on_unload(coordinator.async_add_listener(lambda: _recompute_recipes(hass)))
        _recompute_recipes(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_mealie_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = MealieClient(entry.data[CONF_URL], entry.data[CONF_TOKEN])
    cache_path = Path(hass.config.path(DOMAIN, RECIPE_CACHE_FILENAME))
    coordinator = RecipeCoordinator(hass, client, cache_path, entry)

    hass.data[DOMAIN][RECIPE_COORDINATOR_KEY] = coordinator
    hass.data[DOMAIN][entry.entry_id] = {"recipe_coordinator": coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Not awaited: the first sync fetches every recipe once (thousands of
    # requests for a big library), which is far too long to hold up setup.
    # The sensor reports unknown until it lands.
    entry.async_create_background_task(
        hass, coordinator.async_refresh(), f"{DOMAIN} mealie first sync"
    )
    return True


@callback
def _recompute_recipes(hass: HomeAssistant) -> None:
    recipe_coordinator = hass.data.get(DOMAIN, {}).get(RECIPE_COORDINATOR_KEY)
    if recipe_coordinator is not None:
        recipe_coordinator.async_recompute()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        domain_data = hass.data[DOMAIN]
        domain_data.pop(entry.entry_id, None)
        if entry.data[CONF_STORE_TYPE] == ENTRY_TYPE_MEALIE:
            domain_data.pop(RECIPE_COORDINATOR_KEY, None)
            return unloaded
        _recompute_recipes(hass)
        if domain_data.get(AGGREGATE_OWNER_KEY) == entry.entry_id:
            domain_data[AGGREGATE_OWNER_KEY] = None
            new_owner = None
            for other_entry in hass.config_entries.async_entries(DOMAIN):
                if other_entry.entry_id == entry.entry_id:
                    continue
                if other_entry.state is not ConfigEntryState.LOADED:
                    continue
                other_conf = STORE_REGISTRY.get(other_entry.data[CONF_STORE_TYPE])
                if other_conf is not None and other_conf["kind"] == STORE_KIND_ITEMS:
                    new_owner = other_entry
                    break

            if new_owner is not None:
                _LOGGER.debug("Aggregate ownership handed off to %s", new_owner.entry_id)
                hass.async_create_task(
                    hass.config_entries.async_reload(new_owner.entry_id)
                )
            else:
                # No items-kind entry left to own the aggregate sensors:
                # nothing left to aggregate, so shut the coordinator down
                # and remove it rather than leaving it orphaned in
                # domain_data for a future entry to reuse in a stale state.
                _LOGGER.debug(
                    "No remaining items-kind entries; shutting down aggregate coordinator"
                )
                aggregate_coordinator = domain_data.pop(AGGREGATE_COORDINATOR_KEY, None)
                if aggregate_coordinator is not None:
                    await aggregate_coordinator.async_shutdown()
    return unloaded
