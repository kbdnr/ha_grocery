import json
import pytest
import responses as rsps_lib
from datetime import date
from custom_components.grocery_ads.connectors.ranch99 import (
    Ranch99Connector,
    PROMOTIONS_URL_TEMPLATE,
    DEFAULT_LOCATION_ID,
)

NEXT_DATA = {
    "props": {
        "pageProps": {
            "detail": {
                "storeActivities": [
                    {
                        "id": 1,
                        "name": "Unbeatable Deals",
                        "date": "Sep.18 - Sep.24",
                        "imageUrl": "https://img.awsprod.99ranch.com/aaa.jpeg",
                        "imageText": "{}",
                    },
                    {
                        "id": 2,
                        "name": "Weekend Specials",
                        "date": "Sep.20 - Sep.24",
                        "imageUrl": "https://img.awsprod.99ranch.com/bbb.jpeg",
                        "imageText": "{}",
                    },
                ]
            }
        }
    }
}

MOCK_HTML = (
    '<html><body>'
    f'<script id="__NEXT_DATA__" nonce="abc" type="application/json">{json.dumps(NEXT_DATA)}</script>'
    "</body></html>"
)


@rsps_lib.activate
def test_fetch_returns_flyer_with_all_image_urls():
    rsps_lib.add(rsps_lib.GET, PROMOTIONS_URL_TEMPLATE.format(location_id=DEFAULT_LOCATION_ID), body=MOCK_HTML, status=200)

    flyer = Ranch99Connector().fetch()

    assert flyer.store == "99ranch"
    assert flyer.media_type == "image"
    assert flyer.urls == [
        "https://img.awsprod.99ranch.com/aaa.jpeg",
        "https://img.awsprod.99ranch.com/bbb.jpeg",
    ]
    assert flyer.valid_from == date(date.today().year, 9, 18)
    assert flyer.valid_to == date(date.today().year, 9, 24)


@rsps_lib.activate
def test_fetch_returns_none_when_no_next_data():
    rsps_lib.add(rsps_lib.GET, PROMOTIONS_URL_TEMPLATE.format(location_id=DEFAULT_LOCATION_ID), body="<html><body>nope</body></html>", status=200)
    assert Ranch99Connector().fetch() is None


@rsps_lib.activate
def test_fetch_returns_none_when_no_activities():
    empty = {"props": {"pageProps": {"detail": {"storeActivities": []}}}}
    html = f'<script id="__NEXT_DATA__" nonce="x" type="application/json">{json.dumps(empty)}</script>'
    rsps_lib.add(rsps_lib.GET, PROMOTIONS_URL_TEMPLATE.format(location_id=DEFAULT_LOCATION_ID), body=html, status=200)
    assert Ranch99Connector().fetch() is None


def test_fetch_uses_custom_location_id():
    connector = Ranch99Connector(location_id="9999")
    assert connector.location_id == "9999"


def test_default_location_id_matches_prior_hardcoded_value():
    connector = Ranch99Connector()
    assert connector.location_id == "1007"
