from __future__ import annotations

import re

import requests
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_LOCATION_ID,
    CONF_STORE_TYPE,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
    ENTRY_TYPE_MEALIE,
    LOCATION_POSTAL_CODE,
    MEALIE_ENTRY_NAME,
    STORE_REGISTRY,
)
from .mealie import MealieClient

_POSTAL_CODE_RE = re.compile(r"\d{5}")
# Shown in the form text via placeholders: hassfest rejects URLs written
# directly into translation strings.
_RANCH99_AD_URL_EXAMPLE = "99ranch.com/stores/promotions/1693"
_MEALIE_URL_EXAMPLE = "http://192.168.1.10:9000"


class GroceryAdsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._store_type: str | None = None
        self._locations: dict[str, str] = {}

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            self._store_type = user_input[CONF_STORE_TYPE]
            if self._store_type == ENTRY_TYPE_MEALIE:
                return await self.async_step_mealie()
            conf = STORE_REGISTRY[self._store_type]
            if not conf["needs_location"]:
                return await self._create_entry()
            if conf["location_kind"] == LOCATION_POSTAL_CODE:
                return await self.async_step_postal_code()
            return await self.async_step_store()

        options = {key: conf["name"] for key, conf in STORE_REGISTRY.items()}
        options[ENTRY_TYPE_MEALIE] = MEALIE_ENTRY_NAME
        schema = vol.Schema({vol.Required(CONF_STORE_TYPE): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_postal_code(self, user_input: dict | None = None):
        conf = STORE_REGISTRY[self._store_type]
        errors = {}
        if user_input is not None:
            postal_code = user_input[CONF_LOCATION_ID].strip()
            if not _POSTAL_CODE_RE.fullmatch(postal_code):
                errors[CONF_LOCATION_ID] = "invalid_postal_code"
            else:
                # A ZIP the store has no ad for would otherwise set up fine
                # and just sit at 0 items, so ask for the ad once here.
                connector = conf["connector"](location_id=postal_code)
                try:
                    items = await self.hass.async_add_executor_job(connector.fetch)
                except (requests.RequestException, KeyError, ValueError):
                    errors["base"] = "cannot_connect"
                else:
                    if items:
                        return await self._create_entry(postal_code)
                    errors[CONF_LOCATION_ID] = "no_ad_found"

        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_LOCATION_ID): str}), user_input
        )
        return self.async_show_form(
            step_id="postal_code",
            data_schema=schema,
            errors=errors,
            description_placeholders={"store": conf["name"]},
        )

    async def async_step_store(self, user_input: dict | None = None):
        conf = STORE_REGISTRY[self._store_type]
        if user_input is not None:
            location_id = user_input[CONF_LOCATION_ID]
            return await self._create_entry(location_id, self._locations[location_id])

        try:
            self._locations = await self.hass.async_add_executor_job(
                conf["connector"].list_locations
            )
        except (requests.RequestException, KeyError, TypeError, ValueError):
            self._locations = {}
        if not self._locations:
            return await self.async_step_store_number()

        schema = vol.Schema({vol.Required(CONF_LOCATION_ID): vol.In(self._locations)})
        return self.async_show_form(
            step_id="store",
            data_schema=schema,
            description_placeholders={"store": conf["name"]},
        )

    async def async_step_store_number(self, user_input: dict | None = None):
        """Typed-in fallback for when the store list couldn't be loaded."""
        errors = {}
        if user_input is not None:
            location_id = user_input[CONF_LOCATION_ID].strip()
            if location_id:
                return await self._create_entry(location_id)
            errors[CONF_LOCATION_ID] = "invalid_store_number"

        schema = vol.Schema({vol.Required(CONF_LOCATION_ID): str})
        return self.async_show_form(
            step_id="store_number",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "store": STORE_REGISTRY[self._store_type]["name"],
                "example_url": _RANCH99_AD_URL_EXAMPLE,
            },
        )

    async def async_step_mealie(self, user_input: dict | None = None):
        errors = {}
        if user_input is not None:
            client = MealieClient(user_input[CONF_URL], user_input[CONF_TOKEN])
            try:
                await self.hass.async_add_executor_job(client.group_slug)
            except requests.HTTPError as err:
                unauthorized = err.response is not None and err.response.status_code in (401, 403)
                errors["base"] = "invalid_auth" if unauthorized else "cannot_connect"
            except (requests.RequestException, KeyError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(ENTRY_TYPE_MEALIE)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=MEALIE_ENTRY_NAME,
                    data={
                        CONF_STORE_TYPE: ENTRY_TYPE_MEALIE,
                        CONF_URL: client.url,
                        CONF_TOKEN: user_input[CONF_TOKEN],
                    },
                )

        schema = vol.Schema({vol.Required(CONF_URL): str, vol.Required(CONF_TOKEN): str})
        return self.async_show_form(
            step_id="mealie",
            data_schema=schema,
            errors=errors,
            description_placeholders={"example_url": _MEALIE_URL_EXAMPLE},
        )

    async def _create_entry(self, location_id: str | None = None, location_name: str | None = None):
        name = STORE_REGISTRY[self._store_type]["name"]
        data = {CONF_STORE_TYPE: self._store_type}
        if location_id is not None:
            data[CONF_LOCATION_ID] = location_id
            name = f"{name} ({location_name or location_id})"

        unique_id = (
            self._store_type
            if location_id is None
            else f"{self._store_type}_{location_id}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=name, data=data)
