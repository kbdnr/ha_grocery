from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_LOCATION_ID, CONF_STORE_TYPE, DOMAIN, STORE_REGISTRY


class GroceryAdsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._store_type: str | None = None

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            self._store_type = user_input[CONF_STORE_TYPE]
            if STORE_REGISTRY[self._store_type]["needs_location"]:
                return await self.async_step_location()
            return await self._create_entry()

        options = {key: conf["name"] for key, conf in STORE_REGISTRY.items()}
        schema = vol.Schema({vol.Required(CONF_STORE_TYPE): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_location(self, user_input: dict | None = None):
        if user_input is not None:
            return await self._create_entry(user_input[CONF_LOCATION_ID])

        schema = vol.Schema({vol.Required(CONF_LOCATION_ID): str})
        return self.async_show_form(step_id="location", data_schema=schema)

    async def _create_entry(self, location_id: str | None = None):
        name = STORE_REGISTRY[self._store_type]["name"]
        data = {CONF_STORE_TYPE: self._store_type}
        if location_id is not None:
            data[CONF_LOCATION_ID] = location_id
            name = f"{name} ({location_id})"

        unique_id = (
            self._store_type
            if location_id is None
            else f"{self._store_type}_{location_id}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=name, data=data)
