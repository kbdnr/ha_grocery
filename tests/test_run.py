import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from pathlib import Path
from custom_components.grocery_ads.schema import AdItem, FlyerRef


def make_item(store="hmart", name="Beef"):
    return AdItem(
        store=store, item_name=name, category="Meat", price=10.0,
        unit="lb", sale_type="sale",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


def make_flyer(store="uwajimaya"):
    return FlyerRef(
        store=store, urls=["https://example.com/ad.pdf"], media_type="pdf",
        valid_from=date(2026, 8, 28), valid_to=date(2026, 9, 3),
        scraped_at=datetime(2026, 8, 29, 6, 0, 0),
    )


def test_run_calls_all_connectors(tmp_path):
    from run import run

    mock_items = [make_item()]
    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.FLYER_CONNECTORS", []), \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        mock_connector = MagicMock()
        mock_connector.fetch.return_value = mock_items
        mock_connectors.__iter__ = MagicMock(return_value=iter([mock_connector]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = mock_items
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")

        mock_connector.fetch.assert_called_once()
        mock_db.insert_items.assert_called_once()
        mock_write.assert_called_once()


def test_run_continues_if_one_connector_fails(tmp_path):
    from run import run

    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.FLYER_CONNECTORS", []), \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest"):

        bad = MagicMock()
        bad.fetch.side_effect = Exception("network error")
        good = MagicMock()
        good.fetch.return_value = [make_item()]
        mock_connectors.__iter__ = MagicMock(return_value=iter([bad, good]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = [make_item()]
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")
        good.fetch.assert_called_once()


def test_run_stores_filter_skips_other_connectors(tmp_path):
    from run import run

    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.FLYER_CONNECTORS", []), \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest"):

        hmart = MagicMock()
        hmart.store_id = "hmart"
        hmart.fetch.return_value = [make_item("hmart")]
        other = MagicMock()
        other.store_id = "99ranch"
        other.fetch.return_value = [make_item("99ranch")]
        mock_connectors.__iter__ = MagicMock(return_value=iter([hmart, other]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = [make_item()]
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json", stores=["hmart"])

        hmart.fetch.assert_called_once()
        other.fetch.assert_not_called()


def test_run_returns_1_when_all_attempted_connectors_fail(tmp_path):
    from run import run

    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.FLYER_CONNECTORS", []), \
         patch("run.Database") as mock_db_cls:

        failing = MagicMock()
        failing.store_id = "hmart"
        failing.fetch.side_effect = Exception("network error")
        mock_connectors.__iter__ = MagicMock(return_value=iter([failing]))
        mock_db_cls.return_value = MagicMock()

        result = run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")
        assert result == 1


def test_run_dry_run_does_not_write_files(tmp_path):
    from run import run

    with patch("run.CONNECTORS") as mock_connectors, \
         patch("run.FLYER_CONNECTORS", []), \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        connector = MagicMock()
        connector.store_id = "hmart"
        connector.fetch.return_value = [make_item()]
        mock_connectors.__iter__ = MagicMock(return_value=iter([connector]))

        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json", dry_run=True)

        mock_db.insert_items.assert_not_called()
        mock_write.assert_not_called()


def test_run_calls_flyer_connectors_and_passes_flyers_to_writer(tmp_path):
    from run import run

    with patch("run.CONNECTORS", []), \
         patch("run.FLYER_CONNECTORS") as mock_flyer_connectors, \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        flyer_connector = MagicMock()
        flyer_connector.store_id = "uwajimaya"
        flyer_connector.fetch.return_value = make_flyer("uwajimaya")
        mock_flyer_connectors.__iter__ = MagicMock(return_value=iter([flyer_connector]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = []
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")

        flyer_connector.fetch.assert_called_once()
        _, kwargs = mock_write.call_args
        assert kwargs["flyers"][0].store == "uwajimaya"


def test_run_flyer_connector_failure_does_not_block_others(tmp_path):
    from run import run

    with patch("run.CONNECTORS", []), \
         patch("run.FLYER_CONNECTORS") as mock_flyer_connectors, \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        bad = MagicMock()
        bad.store_id = "99ranch"
        bad.fetch.side_effect = Exception("network error")
        good = MagicMock()
        good.store_id = "uwajimaya"
        good.fetch.return_value = make_flyer("uwajimaya")
        mock_flyer_connectors.__iter__ = MagicMock(return_value=iter([bad, good]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = []
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        result = run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")

        good.fetch.assert_called_once()
        assert result == 0


def test_run_flyer_connector_returning_none_is_not_written(tmp_path):
    from run import run

    with patch("run.CONNECTORS", []), \
         patch("run.FLYER_CONNECTORS") as mock_flyer_connectors, \
         patch("run.Database") as mock_db_cls, \
         patch("run.write_latest") as mock_write:

        connector = MagicMock()
        connector.store_id = "99ranch"
        connector.fetch.return_value = None
        mock_flyer_connectors.__iter__ = MagicMock(return_value=iter([connector]))

        mock_db = MagicMock()
        mock_db.get_latest_items.return_value = []
        mock_db.compute_diff.return_value = {"new": [], "changed": [], "dropped": []}
        mock_db_cls.return_value = mock_db

        run(db_path=tmp_path / "test.db", json_path=tmp_path / "out.json")

        _, kwargs = mock_write.call_args
        assert kwargs["flyers"] == []
