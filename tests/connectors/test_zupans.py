import pytest
import responses as rsps_lib
from datetime import date
from custom_components.grocery_ads.connectors.zupans import ZupansConnector, PROMOTIONS_API

MOCK_CONTENT = """
<h2 class="wp-block-heading">Through September 22</h2>
<article>
  <h3 class="name">Wild King Salmon Fillet</h3>
  <p class="micro tags">local | wild caught</p>
  <p class="link price">$6.99 lb / <strong>save $5 per lb</strong></p>
</article>
<article>
  <h3 class="name">Member Special Coffee</h3>
  <p class="micro tags">member price</p>
  <p class="link price">$8.99 ea</p>
</article>
<article>
  <h3 class="name">Malformed — no price</h3>
  <p class="micro tags">oops</p>
</article>
"""

MOCK_RESPONSE = [
    {
        "id": 53710,
        "slug": "whats-on-sale",
        "modified": "2026-09-21T13:57:42",
        "content": {"rendered": MOCK_CONTENT},
    }
]


@rsps_lib.activate
def test_fetch_parses_articles_into_ad_items():
    rsps_lib.add(
        rsps_lib.GET, PROMOTIONS_API, json=MOCK_RESPONSE, status=200,
    )

    items = ZupansConnector().fetch()

    assert len(items) == 2
    salmon = items[0]
    assert salmon.store == "zupans"
    assert salmon.item_name == "Wild King Salmon Fillet"
    assert salmon.price == 6.99
    assert salmon.unit == "lb"
    assert salmon.sale_type == "sale"
    assert salmon.valid_to == date(2026, 9, 22)

    coffee = items[1]
    assert coffee.item_name == "Member Special Coffee"
    assert coffee.sale_type == "member price"
    assert coffee.unit == "ea"


@rsps_lib.activate
def test_fetch_handles_empty_response():
    rsps_lib.add(rsps_lib.GET, PROMOTIONS_API, json=[], status=200)
    assert ZupansConnector().fetch() == []
