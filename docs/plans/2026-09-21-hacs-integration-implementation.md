# Grocery Ads HACS Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert `grocery_ads/` + `run.py` + `command_line` sensors into a personal-use HACS custom integration at `custom_components/grocery_ads/`, per `docs/plans/2026-09-21-hacs-integration-design.md`.

**Architecture:** Relocate the existing connector/schema/db library unchanged into the integration package. Add a config-flow-driven `STORE_REGISTRY`, one `DataUpdateCoordinator` per config entry (executor-wrapped `fetch()`), a shared SQLite db under `hass.config.path()` for cross-store aggregation, and sensors that mirror today's `latest.json` attribute shapes so the dashboard barely changes.

**Tech Stack:** Python 3, Home Assistant custom integration APIs (`DataUpdateCoordinator`, `ConfigFlow`, `SensorEntity`), `pytest-homeassistant-custom-component` for tests, `requests`/`beautifulsoup4` (unchanged).

---

## Task 1: Add Home Assistant test tooling

**Files:**
- Create: `requirements-ha.txt`

**Step 1: Create the file**

```
homeassistant>=2024.1.0
pytest-homeassistant-custom-component>=0.13.0
```

**Step 2: Install and verify**

Run: `pip install -r requirements-ha.txt`
Expected: installs cleanly (this pulls in `pytest-asyncio`/`pytest-aiohttp` as transitive deps).

Run: `python3 -c "import pytest_homeassistant_custom_component; print('ok')"`
Expected: `ok`

**Step 3: Commit**

```bash
git add requirements-ha.txt
git commit -m "chore: add Home Assistant test tooling for the custom integration"
```

---

## Task 2: Relocate the library into `custom_components/grocery_ads/`

This is mechanical but must happen before any HA-specific code exists, since everything after this task lives inside the integration package and uses relative imports (the idiomatic HA style, and what makes the code work identically under `pytest` and under HA's real component loader).

**Files:**
- Move: `grocery_ads/` → `custom_components/grocery_ads/`
- Modify: every file listed below (import rewrite only)
- Modify: `run.py`
- Modify: `tests/connectors/test_base.py`, `tests/connectors/test_hmart.py`, `tests/connectors/test_new_seasons.py`, `tests/connectors/test_ranch99.py`, `tests/connectors/test_uwajimaya.py`, `tests/connectors/test_zupans.py`, `tests/test_db.py`, `tests/test_run.py`, `tests/test_schema.py`, `tests/test_writer.py`

**Step 1: Move the directory, preserving history**

```bash
git mv grocery_ads custom_components/grocery_ads
```

**Step 2: Rewrite internal imports to relative imports**

In each file below, replace the absolute `grocery_ads.X` import with a relative one:

- `custom_components/grocery_ads/connectors/base.py:2`
  `from grocery_ads.schema import AdItem, FlyerRef` → `from ..schema import AdItem, FlyerRef`
- `custom_components/grocery_ads/connectors/hmart.py:3-4`
  `from grocery_ads.connectors.base import BaseConnector` → `from .base import BaseConnector`
  `from grocery_ads.schema import AdItem` → `from ..schema import AdItem`
- `custom_components/grocery_ads/connectors/new_seasons.py:4-5`, `ranch99.py:5-6`, `uwajimaya.py:5-6`: same pattern (`.base` / `..schema`)
- `custom_components/grocery_ads/connectors/zupans.py:5-6`: same pattern
- `custom_components/grocery_ads/db.py:4`
  `from grocery_ads.schema import AdItem` → `from .schema import AdItem`
- `custom_components/grocery_ads/writer.py:4`
  `from grocery_ads.schema import AdItem, FlyerRef` → `from .schema import AdItem, FlyerRef`

**Step 3: Update `run.py`'s imports to the new absolute path**

`run.py` is not part of the integration package, so it keeps absolute imports — just repointed at the new location:

```python
from custom_components.grocery_ads.connectors.hmart import HMartConnector
from custom_components.grocery_ads.connectors.ranch99 import Ranch99Connector
from custom_components.grocery_ads.connectors.uwajimaya import UwajimayaConnector
from custom_components.grocery_ads.connectors.zupans import ZupansConnector
from custom_components.grocery_ads.connectors.new_seasons import NewSeasonsConnector
from custom_components.grocery_ads.db import Database
from custom_components.grocery_ads.writer import write_latest
```

**Step 4: Update all test imports the same way**

In each of the ten test files listed above, replace `from grocery_ads.X import ...` with `from custom_components.grocery_ads.X import ...`. Also update the two mock-patch targets in `tests/test_run.py` (`patch("run.CONNECTORS")` etc. are already patching `run.*`, so those don't change — only the `from grocery_ads...` import lines do).

**Step 5: Run the full existing suite to confirm nothing broke**

Run: `pytest -v`
Expected: all previously-passing tests still pass (same count as before the move). This is the safety net for the whole relocation — don't proceed until it's green.

**Step 6: Commit**

```bash
git add custom_components run.py tests
git commit -m "refactor: relocate grocery_ads library into custom_components/grocery_ads"
```

---

## Task 3: `const.py` and the store registry

**Files:**
- Create: `custom_components/grocery_ads/const.py`
- Test: `tests/test_const.py`

**Step 1: Write the failing test**

```python
from custom_components.grocery_ads.const import STORE_REGISTRY, STORE_KIND_ITEMS, STORE_KIND_FLYER


def test_registry_has_all_five_stores():
    assert set(STORE_REGISTRY) == {"hmart", "zupans", "99ranch", "uwajimaya", "new_seasons"}


def test_hmart_and_zupans_are_items_kind():
    assert STORE_REGISTRY["hmart"]["kind"] == STORE_KIND_ITEMS
    assert STORE_REGISTRY["zupans"]["kind"] == STORE_KIND_ITEMS


def test_flyer_stores_are_flyer_kind():
    for store_id in ("99ranch", "uwajimaya", "new_seasons"):
        assert STORE_REGISTRY[store_id]["kind"] == STORE_KIND_FLYER


def test_only_99ranch_needs_location():
    for store_id, conf in STORE_REGISTRY.items():
        assert conf["needs_location"] == (store_id == "99ranch")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_const.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.grocery_ads.const'`

**Step 3: Write the implementation**

```python
from .connectors.hmart import HMartConnector
from .connectors.new_seasons import NewSeasonsConnector
from .connectors.ranch99 import Ranch99Connector
from .connectors.uwajimaya import UwajimayaConnector
from .connectors.zupans import ZupansConnector

DOMAIN = "grocery_ads"
DB_FILENAME = "groceries.db"

CONF_STORE_TYPE = "store_type"
CONF_LOCATION_ID = "location_id"

STORE_KIND_ITEMS = "items"
STORE_KIND_FLYER = "flyer"

STORE_REGISTRY = {
    "hmart": {
        "name": "H Mart",
        "connector": HMartConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": False,
    },
    "zupans": {
        "name": "Zupan's Markets",
        "connector": ZupansConnector,
        "kind": STORE_KIND_ITEMS,
        "needs_location": False,
    },
    "99ranch": {
        "name": "99 Ranch Market",
        "connector": Ranch99Connector,
        "kind": STORE_KIND_FLYER,
        "needs_location": True,
    },
    "uwajimaya": {
        "name": "Uwajimaya",
        "connector": UwajimayaConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": False,
    },
    "new_seasons": {
        "name": "New Seasons Market",
        "connector": NewSeasonsConnector,
        "kind": STORE_KIND_FLYER,
        "needs_location": False,
    },
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_const.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add custom_components/grocery_ads/const.py tests/test_const.py
git commit -m "feat: add store registry mapping store types to connectors"
```

---

## Task 4: Make `Ranch99Connector` location-configurable

Today `STORE_ID`/`PROMOTIONS_URL` are hardcoded module constants (per `CLAUDE.md`'s "no zip→store lookup exists yet" note). The config flow needs to be able to pass in a location id per config entry, so this becomes a constructor parameter. Full zip-code→store-ID resolution stays out of scope (per the design doc) — the config flow will just ask for the numeric store ID directly; that's the same information that's hardcoded today, just user-supplied instead of baked in.

**Files:**
- Modify: `custom_components/grocery_ads/connectors/ranch99.py`
- Modify: `tests/connectors/test_ranch99.py`

**Step 1: Write the failing test**

Add to `tests/connectors/test_ranch99.py`:

```python
def test_fetch_uses_custom_location_id():
    connector = Ranch99Connector(location_id="9999")
    assert connector.location_id == "9999"


def test_default_location_id_matches_prior_hardcoded_value():
    connector = Ranch99Connector()
    assert connector.location_id == "1007"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/connectors/test_ranch99.py -v`
Expected: FAIL — `Ranch99Connector() got an unexpected keyword argument 'location_id'` / `AttributeError: 'Ranch99Connector' object has no attribute 'location_id'`

**Step 3: Update the connector**

In `custom_components/grocery_ads/connectors/ranch99.py`, replace the module-level `STORE_ID`/`PROMOTIONS_URL` constants and add an `__init__`:

```python
DEFAULT_LOCATION_ID = "1007"
PROMOTIONS_URL_TEMPLATE = "https://www.99ranch.com/stores/promotions/{location_id}"


class Ranch99Connector(FlyerConnector):
    store_id = "99ranch"

    def __init__(self, location_id: str = DEFAULT_LOCATION_ID):
        self.location_id = location_id

    def fetch(self) -> FlyerRef | None:
        url = PROMOTIONS_URL_TEMPLATE.format(location_id=self.location_id)
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        return self._parse_page(resp.text)
```

(The rest of the class — `_parse_page`, `_widest_date_range`, `_parse_date_range` — is unchanged.)

**Step 4: Fix the existing test's import and mocked URL**

`tests/connectors/test_ranch99.py` currently imports `PROMOTIONS_URL` (the old static constant) and uses it in `@rsps_lib.activate`-decorated tests to register the mock response URL. Update:

```python
from custom_components.grocery_ads.connectors.ranch99 import (
    Ranch99Connector,
    PROMOTIONS_URL_TEMPLATE,
    DEFAULT_LOCATION_ID,
)
```

Anywhere the test body used `PROMOTIONS_URL` to register `responses.add(...)`, replace with `PROMOTIONS_URL_TEMPLATE.format(location_id=DEFAULT_LOCATION_ID)`.

**Step 5: Run test to verify it passes**

Run: `pytest tests/connectors/test_ranch99.py -v`
Expected: PASS, all tests including the two new ones

**Step 6: Commit**

```bash
git add custom_components/grocery_ads/connectors/ranch99.py tests/connectors/test_ranch99.py
git commit -m "feat: make 99 Ranch's store location configurable via constructor"
```

---

## Task 5: `manifest.json` and `hacs.json`

No tests — these are static metadata files HA/HACS read directly.

**Files:**
- Create: `custom_components/grocery_ads/manifest.json`
- Create: `hacs.json`

**Step 1: Write `manifest.json`**

```json
{
  "domain": "grocery_ads",
  "name": "Grocery Ads",
  "version": "0.1.0",
  "config_flow": true,
  "iot_class": "cloud_polling",
  "codeowners": [],
  "requirements": ["requests>=2.31.0", "beautifulsoup4>=4.12.0"],
  "documentation": "https://github.com/YOUR_GITHUB_USER/HA_Grocery",
  "issue_tracker": "https://github.com/YOUR_GITHUB_USER/HA_Grocery/issues"
}
```

Replace `YOUR_GITHUB_USER` with your actual GitHub username/repo path once this is pushed — HACS resolves the repository from where you add it as a custom repository, but `documentation`/`issue_tracker` are shown in HA's integration UI.

**Step 2: Write `hacs.json`**

```json
{
  "name": "Grocery Ads",
  "render_readme": true
}
```

**Step 3: Commit**

```bash
git add custom_components/grocery_ads/manifest.json hacs.json
git commit -m "chore: add manifest.json and hacs.json for HACS custom repository"
```

---

## Task 6: `config_flow.py`

**Files:**
- Create: `custom_components/grocery_ads/config_flow.py`
- Test: `tests/custom_components/grocery_ads/test_config_flow.py`
- Create: `tests/custom_components/__init__.py`, `tests/custom_components/grocery_ads/__init__.py` (empty files so pytest can collect the package)

HA integration tests conventionally live under `tests/components/<domain>/`, but since this isn't a core-HA checkout, `tests/custom_components/grocery_ads/` mirrors the same idea inside this repo.

**Step 1: Create the empty package files**

```bash
mkdir -p tests/custom_components/grocery_ads
touch tests/custom_components/__init__.py tests/custom_components/grocery_ads/__init__.py
```

**Step 2: Write the failing test**

```python
from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow

from custom_components.grocery_ads.const import DOMAIN


@pytest.mark.asyncio
async def test_user_step_shows_store_dropdown(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_hmart_creates_entry_without_location_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "hmart"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "H Mart"
    assert result["data"] == {"store_type": "hmart"}


@pytest.mark.asyncio
async def test_99ranch_asks_for_location_then_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"store_type": "99ranch"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "location"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location_id": "2222"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"store_type": "99ranch", "location_id": "2222"}
```

The `hass` fixture comes from `pytest-homeassistant-custom-component`'s pytest plugin; it's auto-registered once the package is installed (Task 1), no conftest needed for this basic usage.

**Step 3: Run test to verify it fails**

Run: `pytest tests/custom_components/grocery_ads/test_config_flow.py -v`
Expected: FAIL — `homeassistant.data_entry_flow.UnknownHandler` (no config flow registered for `grocery_ads` yet)

**Step 4: Write the implementation**

```python
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
            return self._create_entry()

        options = {key: conf["name"] for key, conf in STORE_REGISTRY.items()}
        schema = vol.Schema({vol.Required(CONF_STORE_TYPE): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_location(self, user_input: dict | None = None):
        if user_input is not None:
            return self._create_entry(user_input[CONF_LOCATION_ID])

        schema = vol.Schema({vol.Required(CONF_LOCATION_ID): str})
        return self.async_show_form(step_id="location", data_schema=schema)

    def _create_entry(self, location_id: str | None = None):
        name = STORE_REGISTRY[self._store_type]["name"]
        data = {CONF_STORE_TYPE: self._store_type}
        if location_id is not None:
            data[CONF_LOCATION_ID] = location_id
            name = f"{name} ({location_id})"
        return self.async_create_entry(title=name, data=data)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/custom_components/grocery_ads/test_config_flow.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add custom_components/grocery_ads/config_flow.py tests/custom_components
git commit -m "feat: add config flow with store dropdown and location step"
```

---

## Task 7: `coordinator.py`

**Files:**
- Create: `custom_components/grocery_ads/coordinator.py`
- Test: `tests/custom_components/grocery_ads/test_coordinator.py`

**Step 1: Write the failing test**

```python
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.grocery_ads.const import STORE_KIND_FLYER, STORE_KIND_ITEMS
from custom_components.grocery_ads.coordinator import AggregateCoordinator, GroceryAdsCoordinator
from custom_components.grocery_ads.schema import AdItem


def make_item():
    return AdItem(
        store="hmart", item_name="Beef", category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_items_kind_coordinator_persists_to_db(hass, tmp_path):
    connector = MagicMock()
    connector.store_id = "hmart"
    connector.fetch.return_value = [make_item()]
    db_path = tmp_path / "groceries.db"

    coordinator = GroceryAdsCoordinator(hass, connector, STORE_KIND_ITEMS, db_path, "entry1")
    await coordinator.async_refresh()

    assert coordinator.data == [make_item()]

    from custom_components.grocery_ads.db import Database
    db = Database(db_path)
    assert len(db.get_latest_items()) == 1


@pytest.mark.asyncio
async def test_flyer_kind_coordinator_does_not_touch_db(hass, tmp_path):
    from custom_components.grocery_ads.schema import FlyerRef

    connector = MagicMock()
    connector.store_id = "99ranch"
    flyer = FlyerRef(
        store="99ranch", urls=["https://example.com/a.jpg"], media_type="image",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )
    connector.fetch.return_value = flyer
    db_path = tmp_path / "groceries.db"

    coordinator = GroceryAdsCoordinator(hass, connector, STORE_KIND_FLYER, db_path, "entry2")
    await coordinator.async_refresh()

    assert coordinator.data == flyer
    assert not db_path.exists()


@pytest.mark.asyncio
async def test_aggregate_coordinator_reads_diff_and_lowest_price(hass, tmp_path):
    db_path = tmp_path / "groceries.db"
    from custom_components.grocery_ads.db import Database
    db = Database(db_path)
    db.insert_items([make_item()])

    coordinator = AggregateCoordinator(hass, db_path)
    await coordinator.async_refresh()

    assert coordinator.data["lowest_price"] == {"Beef": {"store": "hmart", "price": 10.0}}
    assert coordinator.data["diff"]["new"] == [make_item()]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/custom_components/grocery_ads/test_coordinator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.grocery_ads.coordinator'`

**Step 3: Write the implementation**

```python
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
    def __init__(self, hass: HomeAssistant, db_path: str | Path):
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_aggregate", update_interval=DEFAULT_UPDATE_INTERVAL
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/custom_components/grocery_ads/test_coordinator.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add custom_components/grocery_ads/coordinator.py tests/custom_components/grocery_ads/test_coordinator.py
git commit -m "feat: add per-entry and aggregate DataUpdateCoordinators"
```

---

## Task 8: `sensor.py`

**Files:**
- Create: `custom_components/grocery_ads/sensor.py`
- Modify: `custom_components/grocery_ads/const.py` (add two hass.data key constants)
- Test: `tests/custom_components/grocery_ads/test_sensor.py`

**Step 1: Add the two hass.data keys to `const.py`**

Append to `custom_components/grocery_ads/const.py`:

```python
AGGREGATE_COORDINATOR_KEY = "_aggregate_coordinator"
AGGREGATE_OWNER_KEY = "_aggregate_owner"
```

(Underscore-prefixed so they can't collide with a `ConfigEntry.entry_id`, which is also used as a key in the same `hass.data[DOMAIN]` dict — see Task 9.)

**Step 2: Write the failing test**

```python
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.grocery_ads.const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    DOMAIN,
    STORE_KIND_ITEMS,
)
from custom_components.grocery_ads.schema import AdItem
from custom_components.grocery_ads.sensor import async_setup_entry


def make_item():
    return AdItem(
        store="hmart", item_name="Beef", category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 9, 16), valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


@pytest.mark.asyncio
async def test_first_items_entry_also_adds_aggregate_sensors(hass):
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {"store_type": "hmart"}

    coordinator = MagicMock()
    coordinator.data = [make_item()]
    aggregate_coordinator = MagicMock()
    aggregate_coordinator.data = {"lowest_price": {}, "diff": {"new": [], "changed": [], "dropped": []}}

    hass.data[DOMAIN] = {
        "entry1": {"coordinator": coordinator},
        AGGREGATE_COORDINATOR_KEY: aggregate_coordinator,
        AGGREGATE_OWNER_KEY: None,
    }

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert len(added) == 3
    assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] == "entry1"


@pytest.mark.asyncio
async def test_second_items_entry_does_not_duplicate_aggregate_sensors(hass):
    entry = MagicMock()
    entry.entry_id = "entry2"
    entry.data = {"store_type": "zupans"}

    coordinator = MagicMock()
    coordinator.data = [make_item()]

    hass.data[DOMAIN] = {
        "entry2": {"coordinator": coordinator},
        AGGREGATE_COORDINATOR_KEY: MagicMock(),
        AGGREGATE_OWNER_KEY: "entry1",
    }

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert len(added) == 1
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/custom_components/grocery_ads/test_sensor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.grocery_ads.sensor'`

**Step 4: Write the implementation**

```python
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
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/custom_components/grocery_ads/test_sensor.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add custom_components/grocery_ads/sensor.py custom_components/grocery_ads/const.py tests/custom_components/grocery_ads/test_sensor.py
git commit -m "feat: add per-store and aggregate sensor entities"
```

---

## Task 9: `__init__.py` — wire it all together

**Files:**
- Create: `custom_components/grocery_ads/__init__.py`
- Test: `tests/custom_components/grocery_ads/test_init.py`

**Step 1: Write the failing test**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocery_ads.const import AGGREGATE_OWNER_KEY, DOMAIN


@pytest.mark.asyncio
async def test_setup_entry_creates_coordinator_and_forwards_platform(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"store_type": "hmart"})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.grocery_ads.GroceryAdsCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ), patch(
        "custom_components.grocery_ads.AggregateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] is None


@pytest.mark.asyncio
async def test_unload_entry_clears_aggregate_owner_if_it_owned_it(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"store_type": "hmart"})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.grocery_ads.GroceryAdsCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ), patch(
        "custom_components.grocery_ads.AggregateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.data[DOMAIN][AGGREGATE_OWNER_KEY] = entry.entry_id

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/custom_components/grocery_ads/test_init.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.grocery_ads'` (no `__init__.py` means it's not a loadable integration yet)

**Step 3: Write the implementation**

```python
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    CONF_LOCATION_ID,
    CONF_STORE_TYPE,
    DB_FILENAME,
    DOMAIN,
    STORE_REGISTRY,
)
from .coordinator import AggregateCoordinator, GroceryAdsCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {AGGREGATE_OWNER_KEY: None})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {AGGREGATE_OWNER_KEY: None})
    db_path = Path(hass.config.path(DOMAIN, DB_FILENAME))

    entry_conf = STORE_REGISTRY[entry.data[CONF_STORE_TYPE]]
    if entry_conf["needs_location"]:
        connector = entry_conf["connector"](location_id=entry.data[CONF_LOCATION_ID])
    else:
        connector = entry_conf["connector"]()

    coordinator = GroceryAdsCoordinator(hass, connector, entry_conf["kind"], db_path, entry.entry_id)
    await coordinator.async_config_entry_first_refresh()

    if AGGREGATE_COORDINATOR_KEY not in domain_data:
        aggregate_coordinator = AggregateCoordinator(hass, db_path)
        await aggregate_coordinator.async_config_entry_first_refresh()
        domain_data[AGGREGATE_COORDINATOR_KEY] = aggregate_coordinator

    domain_data[entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        domain_data = hass.data[DOMAIN]
        domain_data.pop(entry.entry_id, None)
        if domain_data.get(AGGREGATE_OWNER_KEY) == entry.entry_id:
            domain_data[AGGREGATE_OWNER_KEY] = None
    return unloaded
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/custom_components/grocery_ads/test_init.py -v`
Expected: PASS (2 tests)

**Step 5: Run the whole test suite**

Run: `pytest -v`
Expected: everything passes — original connector/schema/db/writer/run tests (now importing from `custom_components.grocery_ads.*`), plus every new HA test from Tasks 3–9.

**Step 6: Commit**

```bash
git add custom_components/grocery_ads/__init__.py tests/custom_components/grocery_ads/test_init.py
git commit -m "feat: wire up async_setup_entry/async_unload_entry"
```

---

## Task 10: Retire the `command_line` sensors, update the dashboard and docs

**Files:**
- Delete: `ha_config/sensors.yaml`
- Modify: `ha_config/dashboard.yaml`
- Modify: `CLAUDE.md`

**Step 1: Remove the command_line sensor config**

```bash
git rm ha_config/sensors.yaml
```

**Step 2: Update entity references in `dashboard.yaml`**

The markdown card templates currently read `state_attr('sensor.grocery_ads_hmart', 'items')` etc. — those entity ids stay the same (Task 8's `GroceryAdsStoreSensor` unique_id/name scheme produces the same `sensor.grocery_ads_<store>` pattern via `_attr_has_entity_name`+device name), so check each card against the actual entity ids once installed (Task 11) and adjust any that don't match — HA derives the entity id from the device name + entity name, e.g. device "H Mart" + entity name "Ads" → `sensor.h_mart_ads`, which is **not** the same as today's `sensor.grocery_ads_hmart`. Update every `state_attr('sensor.grocery_ads_...', ...)` reference in `ha_config/dashboard.yaml` to match the real entity ids (visible in Settings → Devices & Services → Entities after Task 11's manual install).

**Step 3: Update `CLAUDE.md`**

Replace the "Architecture" tree, "Run on a schedule via cron" section, and the "Home Assistant integration" line in "Build order" to describe the `custom_components/grocery_ads/` integration instead of the cron/`command_line` design — point at `docs/plans/2026-09-21-hacs-integration-design.md` for the details rather than duplicating them.

**Step 4: Commit**

```bash
git add ha_config CLAUDE.md
git commit -m "docs: update dashboard and CLAUDE.md for the HACS integration"
```

---

## Task 11: Manual smoke test

Not automatable — this is the real end-to-end check.

**Step 1: Add as a HACS custom repository**

In HA: HACS → Integrations → ⋮ → Custom repositories → add this repo's URL, category "Integration."

**Step 2: Install and restart**

Install "Grocery Ads" from HACS, restart Home Assistant.

**Step 3: Add config entries**

Settings → Devices & Services → Add Integration → "Grocery Ads" — add H Mart, Zupan's, and at least one flyer store (e.g. Uwajimaya). Confirm each creates a device + `sensor.*_ads` entity with `items` or `urls` attributes populated after the first refresh (check Developer Tools → States).

**Step 4: Add a second 99 Ranch entry with a different location id**

Confirms the "one entry per store instance" design point actually produces two independent devices/entities.

**Step 5: Confirm aggregate sensors appear exactly once**

After adding both H Mart and Zupan's, confirm there's exactly one `sensor.*_lowest_price` and one `sensor.*_new_deals` entity — not two.

**Step 6: Update and paste `ha_config/dashboard.yaml`**

Fix entity ids per Task 10 Step 2, then paste into a new Lovelace dashboard and confirm all four tabs render real data.
