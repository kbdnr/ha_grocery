from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    CONF_STORE_TYPE,
    DOMAIN,
    STORE_KIND_ITEMS,
    STORE_REGISTRY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    domain_data = hass.data[DOMAIN]
    coordinator = domain_data[entry.entry_id]["coordinator"]
    store_type = entry.data[CONF_STORE_TYPE]
    kind = STORE_REGISTRY[store_type]["kind"]

    entities = [GroceryAdsStoreSensor(coordinator, entry, kind)]

    if kind == STORE_KIND_ITEMS and domain_data.get(AGGREGATE_OWNER_KEY) is None:
        domain_data[AGGREGATE_OWNER_KEY] = entry.entry_id
        aggregate_coordinator = domain_data[AGGREGATE_COORDINATOR_KEY]
        entities += [
            GroceryAdsLowestPriceSensor(aggregate_coordinator),
            GroceryAdsNewDealsSensor(aggregate_coordinator),
        ]

    async_add_entities(entities)


class GroceryAdsStoreSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Ads"

    def __init__(self, coordinator, entry: ConfigEntry, kind: str):
        super().__init__(coordinator)
        self._kind = kind
        self._attr_unique_id = f"{entry.entry_id}_ads"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=STORE_REGISTRY[entry.data[CONF_STORE_TYPE]]["name"],
        )

    @property
    def native_value(self):
        data = self.coordinator.data
        if self._kind == STORE_KIND_ITEMS:
            return len(data) if data else 0
        return data.valid_to if data else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data:
            return {}
        if self._kind == STORE_KIND_ITEMS:
            return {"items": [item.to_dict() for item in data]}
        return {"urls": data.urls, "media_type": data.media_type}


class GroceryAdsLowestPriceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Lowest Price"
    _attr_unique_id = f"{DOMAIN}_lowest_price"

    @property
    def native_value(self):
        return len(self.coordinator.data["lowest_price"]) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {"prices": self.coordinator.data["lowest_price"]}


class GroceryAdsNewDealsSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "New Deals"
    _attr_unique_id = f"{DOMAIN}_new_deals"

    @property
    def native_value(self):
        return len(self.coordinator.data["diff"]["new"]) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {"diff": self.coordinator.data["diff"]}
