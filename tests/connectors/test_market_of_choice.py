import responses as rsps_lib
from datetime import date, timedelta
from custom_components.grocery_ads.connectors.market_of_choice import (
    MarketOfChoiceConnector,
    WEEKLY_SPECIALS_REDIRECT,
)

PDF_URL = "https://static.marketofchoice.com/uploads/2023/11/2026-09-18-MoC-Weekly-Specials.pdf"


@rsps_lib.activate
def test_fetch_follows_redirect_to_current_pdf_and_parses_dates():
    rsps_lib.add(
        rsps_lib.GET,
        WEEKLY_SPECIALS_REDIRECT,
        status=301,
        headers={"Location": PDF_URL},
    )
    rsps_lib.add(rsps_lib.GET, PDF_URL, body=b"%PDF-1.4", status=200)

    flyer = MarketOfChoiceConnector().fetch()

    assert flyer.store == "market_of_choice"
    assert flyer.media_type == "pdf"
    assert flyer.urls == [PDF_URL]
    assert flyer.valid_from == date(2026, 9, 18)
    assert flyer.valid_to == date(2026, 9, 18) + timedelta(days=6)


@rsps_lib.activate
def test_fetch_returns_none_when_redirect_target_is_not_a_pdf():
    rsps_lib.add(
        rsps_lib.GET,
        WEEKLY_SPECIALS_REDIRECT,
        status=301,
        headers={"Location": "https://marketofchoice.com/specials/weekly/"},
    )
    rsps_lib.add(
        rsps_lib.GET,
        "https://marketofchoice.com/specials/weekly/",
        body="<html></html>",
        status=200,
    )

    assert MarketOfChoiceConnector().fetch() is None
