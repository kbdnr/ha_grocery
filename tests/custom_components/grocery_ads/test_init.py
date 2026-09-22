from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocery_ads.const import (
    AGGREGATE_COORDINATOR_KEY,
    AGGREGATE_OWNER_KEY,
    DOMAIN,
)
from custom_components.grocery_ads.schema import AdItem


def _item(store: str, name: str = "Beef", price: float = 10.0) -> AdItem:
    return AdItem(
        store=store,
        item_name=name,
        category="Meat",
        price=price,
        unit="lb",
        sale_type="sale",
        valid_from=date(2026, 9, 16),
        valid_to=date(2026, 9, 22),
        scraped_at=datetime(2026, 9, 21, 6, 0, 0),
    )


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
    # sensor.py's aggregate-ownership handshake (Task 8) claims ownership for
    # the first STORE_KIND_ITEMS entry as part of the same forwarded setup.
    assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] == entry.entry_id


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


@pytest.mark.asyncio
async def test_unload_owning_entry_reloads_another_items_entry_to_reclaim_aggregate(hass):
    # entry1 and entry2 are added to hass and set up one at a time (rather
    # than both added before either is set up) to avoid HA's domain-setup
    # auto-cascade, which would set up all pending entries of a newly-loaded
    # domain together and desync this test's sequencing.
    entry1 = MockConfigEntry(domain=DOMAIN, data={"store_type": "hmart"})
    entry1.add_to_hass(hass)

    with patch(
        "custom_components.grocery_ads.GroceryAdsCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ), patch(
        "custom_components.grocery_ads.AggregateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ):
        await hass.config_entries.async_setup(entry1.entry_id)

        entry2 = MockConfigEntry(domain=DOMAIN, data={"store_type": "zupans"})
        entry2.add_to_hass(hass)
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        hass.data[DOMAIN][AGGREGATE_OWNER_KEY] = entry1.entry_id

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", new=AsyncMock()
        ) as mock_reload:
            await hass.config_entries.async_unload(entry1.entry_id)
            await hass.async_block_till_done()

        mock_reload.assert_called_once_with(entry2.entry_id)
        assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] is None

        # Unload entry2 too, still inside the coordinator-refresh mock scope,
        # so hass's own fixture teardown has no loaded items-kind entry left
        # to unload later (which would otherwise, per the logic under test,
        # schedule a real/unmocked reload attempt against the network).
        await hass.config_entries.async_unload(entry2.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_aggregate_coordinator_survives_owner_handoff(hass):
    # Unlike the test above, this does NOT mock ConfigEntries.async_reload or
    # the coordinators' async_config_entry_first_refresh -- it lets the real
    # reload path run end to end, and only stubs the connectors' network
    # calls. This is what actually exercises whether the resulting aggregate
    # coordinator is still functional after a handoff, which is exactly what
    # the ContextVar auto-bind bug broke (self.config_entry got bound to
    # whichever entry was mid-setup when AggregateCoordinator() was
    # constructed, so *that* entry's unload silently and permanently killed
    # the aggregate coordinator via DataUpdateCoordinator's
    # async_on_unload(self.async_shutdown) registration, regardless of
    # aggregate ownership).
    with patch(
        "custom_components.grocery_ads.connectors.hmart.HMartConnector.fetch",
        return_value=[_item("hmart")],
    ), patch(
        "custom_components.grocery_ads.connectors.zupans.ZupansConnector.fetch",
        return_value=[_item("zupans")],
    ):
        entry1 = MockConfigEntry(domain=DOMAIN, data={"store_type": "hmart"})
        entry1.add_to_hass(hass)
        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

        entry2 = MockConfigEntry(domain=DOMAIN, data={"store_type": "zupans"})
        entry2.add_to_hass(hass)
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] == entry1.entry_id
        aggregate_coordinator = hass.data[DOMAIN][AGGREGATE_COORDINATOR_KEY]
        assert aggregate_coordinator.last_update_success is True

        await hass.config_entries.async_unload(entry1.entry_id)
        await hass.async_block_till_done()

        # Ownership handed off to entry2 via a REAL (unmocked) reload.
        assert hass.data[DOMAIN][AGGREGATE_OWNER_KEY] == entry2.entry_id
        # The SAME coordinator object survived -- it was not torn down as a
        # side effect of entry1 (its unrelated "creator" entry) unloading.
        assert hass.data[DOMAIN][AGGREGATE_COORDINATOR_KEY] is aggregate_coordinator
        assert aggregate_coordinator._shutdown_requested is False

        # And it must still be genuinely refreshable, not a silent no-op.
        aggregate_coordinator.last_update_success = False
        await aggregate_coordinator.async_refresh()
        assert aggregate_coordinator.last_update_success is True

        # Clean up so hass's fixture teardown has nothing left to unload.
        await hass.config_entries.async_unload(entry2.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_unload_last_items_entry_shuts_down_aggregate_coordinator(hass):
    # The legitimate cleanup path: when the LAST items-kind entry unloads,
    # there is nothing left to aggregate, so the aggregate coordinator
    # should actually be shut down and removed -- not left dangling.
    with patch(
        "custom_components.grocery_ads.connectors.hmart.HMartConnector.fetch",
        return_value=[_item("hmart")],
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"store_type": "hmart"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        aggregate_coordinator = hass.data[DOMAIN][AGGREGATE_COORDINATOR_KEY]

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert AGGREGATE_COORDINATOR_KEY not in hass.data[DOMAIN]
        assert aggregate_coordinator._shutdown_requested is True
