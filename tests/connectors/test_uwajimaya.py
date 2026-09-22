import pytest
import responses as rsps_lib
from datetime import date, timedelta
from custom_components.grocery_ads.connectors.uwajimaya import UwajimayaConnector, WEEKLY_AD_PAGE

MOCK_HTML = """
<html><body>
<div class="section section-button other-stuff">
  <a class="button-bar blue" href="https://www.uwajimaya.com/wp-content/uploads/2026/09/WeeklyAd-09.16.26.pdf" target="_blank">
    <div class="a1 text">Download PDF</div>
  </a>
</div>
</body></html>
"""


@rsps_lib.activate
def test_fetch_returns_flyer_with_pdf_url_and_dates():
    rsps_lib.add(rsps_lib.GET, WEEKLY_AD_PAGE, body=MOCK_HTML, status=200)

    flyer = UwajimayaConnector().fetch()

    assert flyer.store == "uwajimaya"
    assert flyer.media_type == "pdf"
    assert flyer.urls == [
        "https://www.uwajimaya.com/wp-content/uploads/2026/09/WeeklyAd-09.16.26.pdf"
    ]
    assert flyer.valid_from == date(2026, 9, 16)
    assert flyer.valid_to == date(2026, 9, 16) + timedelta(days=6)


@rsps_lib.activate
def test_fetch_returns_none_when_no_pdf_link():
    rsps_lib.add(rsps_lib.GET, WEEKLY_AD_PAGE, body="<html><body>no link here</body></html>", status=200)
    assert UwajimayaConnector().fetch() is None
