import json

import pytest
import requests
import responses as rsps_lib

from custom_components.grocery_ads.mealie import MealieClient, load_cache, save_cache, sync_recipes

URL = "https://mealie.example.com"


def _page(items, page=1, total_pages=1):
    return {"page": page, "per_page": 500, "total": len(items), "total_pages": total_pages, "items": items}


def _recipe(*food_ids):
    return {
        "recipeIngredient": [
            {"food": {"id": food_id} if food_id else None, "note": "x"} for food_id in food_ids
        ]
    }


def test_client_strips_trailing_slash_and_builds_recipe_urls():
    client = MealieClient(URL + "/", "token")
    assert client.url == URL
    assert client.recipe_url("home", "salmon-dinner") == f"{URL}/g/home/r/salmon-dinner"


@rsps_lib.activate
def test_group_slug_sends_the_token():
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/users/self", json={"groupSlug": "home"}, status=200)

    assert MealieClient(URL, "secret").group_slug() == "home"
    assert rsps_lib.calls[0].request.headers["Authorization"] == "Bearer secret"


@rsps_lib.activate
def test_group_slug_raises_on_bad_token():
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/users/self", json={"detail": "nope"}, status=401)

    with pytest.raises(requests.HTTPError):
        MealieClient(URL, "wrong").group_slug()


@rsps_lib.activate
def test_foods_walks_every_page():
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/foods", json=_page([{"id": "a"}], 1, 2), status=200)
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/foods", json=_page([{"id": "b"}], 2, 2), status=200)

    assert MealieClient(URL, "token").foods() == [{"id": "a"}, {"id": "b"}]
    assert "page=2" in rsps_lib.calls[1].request.url


@rsps_lib.activate
def test_recipe_food_ids_skips_unparsed_ingredients_and_duplicates():
    rsps_lib.add(
        rsps_lib.GET, f"{URL}/api/recipes/stew", json=_recipe("beef", None, "onion", "beef"), status=200,
    )

    assert MealieClient(URL, "token").recipe_food_ids("stew") == ["beef", "onion"]


@rsps_lib.activate
def test_sync_fetches_new_and_changed_recipes_only_and_drops_removed_ones(tmp_path):
    cache_path = tmp_path / "grocery_ads" / "mealie_recipes.json"
    cache = {
        "unchanged": {"name": "Unchanged", "updated": "t1", "foods": ["butter"]},
        "changed": {"name": "Changed", "updated": "t1", "foods": ["egg"]},
        "deleted": {"name": "Deleted", "updated": "t1", "foods": ["milk"]},
    }
    rsps_lib.add(
        rsps_lib.GET,
        f"{URL}/api/recipes",
        json=_page([
            {"slug": "unchanged", "name": "Unchanged", "updatedAt": "t1"},
            {"slug": "changed", "name": "Changed", "updatedAt": "t2"},
            {"slug": "new", "name": "New", "updatedAt": "t1"},
        ]),
        status=200,
    )
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/recipes/changed", json=_recipe("egg", "cheese"), status=200)
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/recipes/new", json=_recipe("salmon"), status=200)

    recipes = sync_recipes(MealieClient(URL, "token"), cache, cache_path)

    assert recipes == {
        "unchanged": {"name": "Unchanged", "updated": "t1", "foods": ["butter"]},
        "changed": {"name": "Changed", "updated": "t2", "foods": ["egg", "cheese"]},
        "new": {"name": "New", "updated": "t1", "foods": ["salmon"]},
    }
    # one list call + the two recipes that needed fetching; "unchanged" wasn't re-read
    assert len(rsps_lib.calls) == 3
    assert load_cache(cache_path) == recipes


@rsps_lib.activate
def test_sync_keeps_the_cached_copy_of_a_recipe_that_fails_to_fetch(tmp_path):
    cache = {"flaky": {"name": "Flaky", "updated": "t1", "foods": ["egg"]}}
    rsps_lib.add(
        rsps_lib.GET,
        f"{URL}/api/recipes",
        json=_page([
            {"slug": "flaky", "name": "Flaky", "updatedAt": "t2"},
            {"slug": "broken-new", "name": "Broken New", "updatedAt": "t1"},
        ]),
        status=200,
    )
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/recipes/flaky", status=500)
    rsps_lib.add(rsps_lib.GET, f"{URL}/api/recipes/broken-new", status=500)

    recipes = sync_recipes(MealieClient(URL, "token"), cache, tmp_path / "cache.json")

    # still on its old timestamp, so the next sync tries it again
    assert recipes == {"flaky": {"name": "Flaky", "updated": "t1", "foods": ["egg"]}}


def test_load_cache_returns_empty_for_missing_or_corrupt_file(tmp_path):
    assert load_cache(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("{not json")
    assert load_cache(tmp_path / "bad.json") == {}


def test_save_cache_round_trips(tmp_path):
    path = tmp_path / "nested" / "cache.json"
    save_cache(path, {"a": {"name": "A", "updated": "t", "foods": []}})
    assert json.loads(path.read_text()) == {"recipes": {"a": {"name": "A", "updated": "t", "foods": []}}}
