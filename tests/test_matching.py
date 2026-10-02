from types import SimpleNamespace

import pytest

from custom_components.grocery_ads.matching import FoodIndex, find_offers, rank_recipes


def _food(name, label="Vegetables & Greens", aliases=(), plural=None):
    return {
        "id": name,  # the name doubles as the id to keep assertions readable
        "name": name,
        "pluralName": plural,
        "aliases": [{"name": alias} for alias in aliases],
        "label": {"name": label} if label else None,
    }


FOODS = [
    _food("chicken", "Poultry"),
    _food("chicken breast", "Poultry", aliases=["boneless skinless chicken breast"]),
    _food("ground beef", "Meats"),
    _food("ground turkey", "Poultry"),
    _food("ribeye steak", "Meats"),
    _food("salmon", "Fish"),
    _food("shrimp", "Seafood & Seaweed"),
    _food("tomato", plural="tomatoes"),
    _food("broccoli"),
    _food("pumpkin"),
    _food("orange", "Fruits"),
    _food("strawberry", "Berries", plural="strawberries"),
    _food("raspberry", "Berries", plural="raspberries"),
    _food("cheese", "Cheese"),
    _food("cream", "Dairy & Eggs"),
    _food("ice cream", "Desserts & Sweet Snacks"),
    _food("butter", "Dairy & Eggs"),
    _food("egg", "Dairy & Eggs"),
    _food("orange juice", "Beverages"),
    _food("carrot juice", "Beverages"),
    _food("pasta", "Pasta"),
    _food("no label food", None),
]


@pytest.fixture
def index():
    return FoodIndex(FOODS)


@pytest.mark.parametrize(
    "item_name, expected",
    [
        # the food is the last thing in the name, whatever brand comes first
        ("Foster Farms Fresh Boneless Skinless Chicken Breast Fillets", {"chicken breast"}),
        ("Fresh Open Nature® Boneless Skinless Chicken Breasts", {"chicken breast"}),
        ("Russet Tomatoes 5 lb. bag", {"tomato"}),
        # ...so a product that merely contains the food doesn't match it
        ("Foster Farms Chicken Breast Nuggets 33.6 oz.", set()),
        ("Tostitos Tortilla Chips", set()),
        # trailing cut/packaging words are looked past, unless they're part of the food
        ("Aqua Star Salmon Fillets", {"salmon"}),
        ("Ribeye Steaks", {"ribeye steak"}),
        ("Broccoli Crowns", {"broccoli"}),
        ("Fresh Northwest Cooked Shrimp Meat", {"shrimp"}),
        # qualifiers after the head noun
        ("Tomatoes on the Vine", {"tomato"}),
        # each alternative is its own product
        ("Fresh Signature SELECT® Ground Beef or Jennie-O Ground Turkey 93% Lean.", {"ground beef", "ground turkey"}),
        ("Strawberries 1 lb., Raspberries or Blackberries 6 oz.", {"strawberry", "raspberry"}),
        # "Orange or Carrot Juice" is orange juice, not oranges
        ("Bolthouse Farms Orange or Carrot Juice, 52 oz.", {"orange juice", "carrot juice"}),
        # longest phrase wins
        ("Tillamook Ice Cream", {"ice cream"}),
        # not ingredients: non-food, flavours, pairs, chocolate shapes
        ("Gold Bond Hand Cream", set()),
        ("Prebiotic Soda Orange", set()),
        ("Nissin, Hot & Spicy Noodle Bowl, Chicken, 3.32 oz, 18-Count", set()),
        ("Kraft Mac & Cheese", set()),
        ("Dove Chocolate Pumpkins", set()),
        ("", set()),
    ],
)
def test_match(index, item_name, expected):
    assert index.match(item_name) == expected


def test_index_tracks_which_foods_are_fresh(index):
    assert "salmon" in index.fresh
    assert "pasta" not in index.fresh
    assert "no label food" not in index.fresh


def _item(store, name, price):
    return SimpleNamespace(store=store, item_name=name, price=price)


def test_find_offers_groups_by_food_cheapest_first(index):
    offers = find_offers(
        [
            _item("safeway", "Aqua Star Salmon Fillets", 9.99),
            _item("fred_meyer", "Fresh Wild-Caught Coho Salmon Fillets", 7.99),
            _item("safeway", "Brawny Paper Towels", 5.99),
        ],
        index,
    )

    assert list(offers) == ["salmon"]
    assert [offer["store"] for offer in offers["salmon"]] == ["fred_meyer", "safeway"]
    assert offers["salmon"][0] == {
        "store": "fred_meyer", "item": "Fresh Wild-Caught Coho Salmon Fillets", "price": 7.99,
    }


def _offers(*food_ids):
    return {food_id: [{"store": "safeway", "item": food_id.title(), "price": 1.0}] for food_id in food_ids}


def test_rank_recipes_puts_rare_on_sale_ingredients_ahead_of_staples(index):
    recipes = {
        "salmon-dinner": {"name": "Salmon Dinner", "foods": ["salmon", "butter", "pasta"]},
        "scrambled-eggs": {"name": "Scrambled Eggs", "foods": ["egg", "butter"]},
        "omelette": {"name": "Omelette", "foods": ["egg", "butter", "cheese"]},
        "buttered-pasta": {"name": "Buttered Pasta", "foods": ["butter", "pasta"]},
    }

    ranked = rank_recipes(recipes, _offers("salmon", "butter", "egg"), index)

    # butter is in every recipe, so it carries no weight on its own
    assert [recipe["slug"] for recipe in ranked][0] == "salmon-dinner"
    top = ranked[0]
    assert top["name"] == "Salmon Dinner"
    assert (top["on_sale"], top["ingredients"]) == (2, 3)
    assert [match["food"] for match in top["matches"]] == ["salmon", "butter"]
    assert top["matches"][0]["store"] == "safeway"


def test_rank_recipes_needs_a_fresh_ingredient_on_sale(index):
    recipes = {
        "buttered-pasta": {"name": "Buttered Pasta", "foods": ["butter", "pasta"]},
        "plain-pasta": {"name": "Plain Pasta", "foods": ["pasta"]},
    }

    ranked = rank_recipes(recipes, _offers("pasta"), index)

    assert ranked == []


def test_rank_recipes_ignores_recipes_with_no_parsed_foods(index):
    recipes = {
        "unparsed": {"name": "Unparsed", "foods": []},
        "salmon-dinner": {"name": "Salmon Dinner", "foods": ["salmon"]},
    }

    ranked = rank_recipes(recipes, _offers("salmon"), index)

    assert [recipe["slug"] for recipe in ranked] == ["salmon-dinner"]
