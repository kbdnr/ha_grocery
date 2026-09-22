import pytest
import responses as rsps_lib
from datetime import date
from custom_components.grocery_ads.connectors.new_seasons import NewSeasonsConnector, WEEKLY_AD_PAGE

PDF_URL = (
    "https://www.newseasonsmarket.com/getContentAsset/909e0a2b-81f2-4b95-bc9b-3bb0eb220d6b/"
    "dfc3d011-8f63-43f6-9ed8-4b444333a1d0/NSM-Sales-Flyer-091626-092226-(R).pdf?language=en"
)

MOCK_HTML = f"""
<html><body>
<h2>Print Weekly Flyer PDF</h2>
<a href="{PDF_URL}">Weekly Flyer 9/16-9/22</a>
</body></html>
"""


@rsps_lib.activate
def test_fetch_returns_flyer_with_pdf_url_and_dates():
    rsps_lib.add(rsps_lib.GET, WEEKLY_AD_PAGE, body=MOCK_HTML, status=200)

    flyer = NewSeasonsConnector().fetch()

    assert flyer.store == "new_seasons"
    assert flyer.media_type == "pdf"
    assert flyer.urls == [PDF_URL]
    assert flyer.valid_from == date(2026, 9, 16)
    assert flyer.valid_to == date(2026, 9, 22)


@rsps_lib.activate
def test_fetch_returns_none_when_no_pdf_link():
    rsps_lib.add(rsps_lib.GET, WEEKLY_AD_PAGE, body="<html><body>no link here</body></html>", status=200)
    assert NewSeasonsConnector().fetch() is None
