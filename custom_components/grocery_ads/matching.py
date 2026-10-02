"""Matches ad item names to Mealie foods, and ranks recipes by what's on sale.

Pure Python on purpose (no Home Assistant, no I/O) so it can be tested and
tuned against saved ad/food data without a running instance.

The join key is Mealie's own food vocabulary: every food's name, plural
name and aliases become phrases, and an ad item matches a food when one of
those phrases is the *last* thing in the item name. English product names
put the head noun last, so "Foster Farms Boneless Skinless Chicken Breast
Fillets" is chicken breast, while "Chicken Breast Nuggets" is not -- which
is what keeps processed products from matching their main ingredient.
"""
from __future__ import annotations

import math
import re

# Mealie food labels where an ad hit says something about what to cook this
# week. A recipe needs at least one of these on sale to be listed at all;
# pantry and snack matches (olive oil, pasta, cookies) only add detail.
FRESH_LABELS = frozenset({
    "Meats", "Poultry", "Fish", "Seafood & Seaweed", "Vegetables & Greens",
    "Fruits", "Berries", "Mushrooms", "Cheese", "Dairy & Eggs",
})

_SIZE_RE = re.compile(
    r"\b\d[\d.,/-]*\s*(?:-\s*\d[\d.]*\s*)?"
    r"(?:fl\.?\s*oz|oz|lbs?|ct|count|pk|packs?|g|kg|ml|l|qt|gal|pt|inch|in)\b\.?",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z][a-z'-]*")
_SEGMENT_RE = re.compile(r"\s+or\s+|[,;/]", re.IGNORECASE)

# Trailing words that describe the cut or the packaging, not the product.
_TAIL_NOISE = frozenset({
    "fillet", "portion", "tray", "bag", "pack", "bunch", "value", "family",
    "selected", "variety", "each", "whole", "half", "cut", "piece", "tender",
    "roast", "steak", "chop", "loin", "meat", "ea", "lb", "per", "frozen",
    "fresh", "bone-in", "boneless", "skinless", "gallon", "quart", "pint",
    "dozen", "pound", "quarter", "stick", "clamshell", "carton", "can",
    "bottle", "btl", "jar", "box", "crown", "heart", "link", "lean",
})
# What follows these is a qualifier ("Tomatoes on the Vine", "Chicken Breast
# with Rib Meat"), so the head noun is whatever comes before.
_QUALIFIER_STARTS = frozenset({"with", "on", "in"})
# Words that mean the item isn't an ingredient even when a food name ends
# it: either it isn't food ("Hand Cream"), or the food word is a flavour
# ("Prebiotic Soda Orange", "Energy Drink, Kiwi Guava").
_NOT_INGREDIENT = frozenset({
    "hand", "body", "face", "skin", "lotion", "shampoo", "conditioner",
    "soap", "detergent", "moisturizer", "candle", "scented", "toothpaste",
    "deodorant", "pet", "soda", "drink", "energy", "gum",
    "gummy", "gummi", "candy", "flavor", "flavored", "vitamin", "supplement",
    "hair", "care",
})


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("oes"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("®", "").replace("™", "").replace("&", " and ")
    text = _SIZE_RE.sub(" ", text)
    words = (word.strip("'-") for word in _WORD_RE.findall(text))
    return [_singular(word) for word in words if word]


class FoodIndex:
    """Phrase lookup over Mealie foods (as returned by GET /api/foods)."""

    def __init__(self, foods: list[dict]):
        self.names: dict[str, str] = {}
        self.fresh: set[str] = set()
        self._phrases: dict[tuple[str, ...], str] = {}
        for food in foods:
            food_id = food["id"]
            self.names[food_id] = food["name"]
            if ((food.get("label") or {}).get("name")) in FRESH_LABELS:
                self.fresh.add(food_id)
            names = [food["name"], food.get("pluralName")]
            names += [alias.get("name") for alias in food.get("aliases") or []]
            for name in names:
                phrase = tuple(tokenize(name or ""))
                if phrase:
                    self._phrases.setdefault(phrase, food_id)
        self._longest = max((len(phrase) for phrase in self._phrases), default=0)

    def _ending(self, tokens: list[str]) -> tuple[int, str] | None:
        """The longest food phrase that ends `tokens`: (start index, food id).

        Nothing if it's the second half of a pair ("Mac & Cheese", "Peanut
        Butter and Jelly") or a chocolate shape ("Chocolate Pumpkins") --
        that's a product of its own, not the food.
        """
        for size in range(min(self._longest, len(tokens)), 0, -1):
            food_id = self._phrases.get(tuple(tokens[-size:]))
            if food_id:
                start = len(tokens) - size
                if start and tokens[start - 1] in ("and", "chocolate"):
                    return None
                return start, food_id
        return None

    def match(self, item_name: str) -> set[str]:
        """Ids of the foods this ad item is. Ad items often list several
        products ("Ground Beef or Jennie-O Ground Turkey"), so each
        alternative is matched on its own."""
        if _NOT_INGREDIENT.intersection(tokenize(item_name)):
            return set()

        parts = _SEGMENT_RE.split(item_name)
        # "Noodle Bowl, Chicken, 18-Count": with no "or" in the name, a lone
        # word after a comma is the flavour, not another product.
        lists_alternatives = re.search(r"\sor\s", item_name, re.IGNORECASE) is not None
        segments = []
        for position, part in enumerate(parts):
            tokens = self._head(tokenize(part))
            if position and len(tokens) == 1 and not lists_alternatives:
                continue
            if tokens:
                segments.append(tokens)

        matched = set()
        for position, tokens in enumerate(segments):
            following = segments[position + 1] if position + 1 < len(segments) else []
            food_id = self._elided(tokens, following) or self._food(tokens)
            if food_id:
                matched.add(food_id)
        return matched

    @staticmethod
    def _head(tokens: list[str]) -> list[str]:
        for position, token in enumerate(tokens):
            if token in _QUALIFIER_STARTS and position > 0:
                return tokens[:position]
        return tokens

    def _food(self, tokens: list[str]) -> str | None:
        """The food that ends `tokens`, looking past trailing cut/packaging
        words only when the name doesn't match with them ("Ribeye Steaks"
        is ribeye steak; "Salmon Fillets" is salmon)."""
        while tokens:
            ending = self._ending(tokens)
            if ending:
                return ending[1]
            if tokens[-1] not in _TAIL_NOISE:
                return None
            tokens = tokens[:-1]
        return None

    def _elided(self, tokens: list[str], following: list[str]) -> str | None:
        """"Orange or Carrot Juice" means orange juice, not oranges: when an
        alternative completes into a longer food by borrowing the tail of
        the next one, that longer food is what's on sale."""
        while following and following[-1] in _TAIL_NOISE:
            following = following[:-1]
        for skip in range(1, len(following)):
            ending = self._ending(tokens + following[skip:])
            if ending and ending[0] < len(tokens):
                return ending[1]
        return None


def find_offers(items, index: FoodIndex) -> dict[str, list[dict]]:
    """Groups ad items by the food they match, cheapest first.

    `items` are AdItems (anything with store/item_name/price).
    """
    offers: dict[str, list[dict]] = {}
    for item in items:
        for food_id in index.match(item.item_name):
            offers.setdefault(food_id, []).append(
                {"store": item.store, "item": item.item_name, "price": item.price}
            )
    for food_offers in offers.values():
        food_offers.sort(key=lambda offer: offer["price"])
    return offers


def rank_recipes(
    recipes: dict[str, dict],
    offers: dict[str, list[dict]],
    index: FoodIndex,
) -> list[dict]:
    """Recipes with a fresh ingredient on sale, best first.

    `recipes` maps slug -> {"name": ..., "foods": [food ids]}. Each on-sale
    ingredient counts by how rare it is across all recipes, so butter and
    eggs (in the ad every week, in a thousand recipes) don't outrank the
    week's actual specials. Ties go to the recipe with more of its
    ingredients covered.
    """
    usable = {slug: recipe for slug, recipe in recipes.items() if recipe.get("foods")}
    used_in: dict[str, int] = {}
    for recipe in usable.values():
        for food_id in set(recipe["foods"]):
            used_in[food_id] = used_in.get(food_id, 0) + 1
    rarity = {food_id: math.log(len(usable) / count) for food_id, count in used_in.items()}

    ranked = []
    for slug, recipe in usable.items():
        food_ids = set(recipe["foods"])
        on_sale = food_ids & offers.keys()
        fresh_on_sale = on_sale & index.fresh
        if not fresh_on_sale:
            continue
        score = sum(rarity[food_id] for food_id in fresh_on_sale)
        total = sum(rarity[food_id] for food_id in food_ids)
        covered = sum(rarity[food_id] for food_id in on_sale) / total if total else 0.0
        matches = [
            {"food": index.names.get(food_id, food_id), **offers[food_id][0]}
            for food_id in sorted(on_sale, key=lambda food_id: (-rarity[food_id], food_id))
        ]
        ranked.append((score, covered, slug, {
            "slug": slug,
            "name": recipe.get("name") or slug,
            "on_sale": len(on_sale),
            "ingredients": len(food_ids),
            "matches": matches,
        }))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [row[3] for row in ranked]
