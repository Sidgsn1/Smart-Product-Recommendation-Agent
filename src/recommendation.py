"""Recommendation logic for products."""

from difflib import get_close_matches
from statistics import median
from typing import Any, Dict, List, Optional, Tuple


def score_product(
    product: Dict[str, Any],
    max_budget: Optional[float] = None,
    category_prices: Optional[List[float]] = None,
) -> float:
    """
    Compute a weighted recommendation score for each product.

    Priority:
    - Rating (highest)
    - Product quality (high)
    - Discount (medium)
    - Price (lower priority, especially when budget is high)
    """
    rating = float(product.get("rating", 0))
    discount = float(product.get("discountPercentage", 0))
    price = float(product.get("price", 0))
    stock = float(product.get("stock", 0))  # small availability signal

    # --- Quality and price context inside the current category ---
    # We use category price stats to understand if an item is premium or budget.
    prices = category_prices or [price]
    min_price = min(prices) if prices else price
    max_price = max(prices) if prices else price
    median_price = median(prices) if prices else price
    price_span = max(max_price - min_price, 1.0)

    # Price percentile in category: 0 -> cheapest, 1 -> most expensive.
    price_percentile = (price - min_price) / price_span

    # Base quality: mostly rating + a tiny stock contribution.
    quality_score = (rating / 5.0) * 10.0 + min(stock, 100.0) * 0.01

    # If budget is high, add premium bonus so better products surface first.
    high_budget_mode = bool(max_budget is not None and max_budget >= (median_price * 1.2))
    premium_bonus = 0.0
    if high_budget_mode:
        premium_bonus = price_percentile * 2.0

    # Price effect:
    # - For normal budgets: cheaper gets some bonus.
    # - For high budgets: price effect is very small.
    if high_budget_mode:
        price_component = (1.0 - price_percentile) * 0.2
    else:
        price_component = (1.0 - price_percentile) * 1.5

    # Strong penalty for very low ratings so they cannot top the list.
    low_rating_penalty = 0.0
    if rating < 3.0:
        low_rating_penalty = (3.0 - rating) * 4.0

    # Final weighted score.
    # Rating dominates, then quality, then discount, then price.
    score = (
        (rating * 8.0)
        + (quality_score * 2.0)
        + (discount * 0.6)
        + price_component
        + premium_bonus
        - low_rating_penalty
    )
    return score


def _normalize(text: str) -> str:
    """
    Normalize text for matching comparisons.
    """
    return text.lower().strip().replace("-", " ").replace("_", " ")


def _category_aliases() -> Dict[str, str]:
    """
    Common user terms mapped to real DummyJSON category names.
    """
    return {
        "phone": "smartphones",
        "mobile": "smartphones",
        "cell phone": "smartphones",
        "motocycle": "motorcycle",
        "bike": "motorcycle",
        "laptop": "laptops",
    }


def resolve_category(user_input: Optional[str], available_categories: List[str]) -> Optional[str]:
    """
    Resolve user category input to the closest available category.

    Strategy:
    - exact match (case-insensitive)
    - alias mapping
    - partial contains match
    - fuzzy match (difflib)
    """
    if not user_input:
        return None

    normalized_input = _normalize(user_input)
    if not normalized_input:
        return None

    categories_map = {_normalize(c): c for c in available_categories}

    # 1) exact match
    if normalized_input in categories_map:
        return categories_map[normalized_input]

    # 2) alias match
    alias_map = _category_aliases()
    alias_value = alias_map.get(normalized_input)
    if alias_value:
        for c in available_categories:
            if _normalize(c) == _normalize(alias_value):
                return c

    # 3) partial match
    partial_matches = [
        original
        for original in available_categories
        if normalized_input in _normalize(original)
        or _normalize(original) in normalized_input
    ]
    if partial_matches:
        return partial_matches[0]

    # 4) fuzzy typo correction
    normalized_categories = list(categories_map.keys())
    fuzzy = get_close_matches(normalized_input, normalized_categories, n=1, cutoff=0.6)
    if fuzzy:
        return categories_map[fuzzy[0]]

    return None


def suggest_closest_category(
    user_input: Optional[str], available_categories: List[str]
) -> Optional[str]:
    """
    Suggest the closest category when exact recommendation set is empty.
    """
    return resolve_category(user_input, available_categories)


def recommend_products(
    products: List[Dict[str, Any]],
    category: Optional[str] = None,
    max_budget: Optional[float] = None,
    top_n: int = 5,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Filter and rank products based on user preferences.
    """
    filtered = products
    matched_category: Optional[str] = None

    # Filter by category if user provided one.
    if category:
        available_categories = sorted(
            {str(p.get("category", "")).strip() for p in products if p.get("category")}
        )
        matched_category = resolve_category(category, available_categories)

        # If category is not resolved, keep an empty set for now.
        if not matched_category:
            filtered = []
        else:
            matched_normalized = _normalize(matched_category)
            filtered = [
                p
                for p in filtered
                if _normalize(str(p.get("category", ""))) == matched_normalized
            ]

    # Filter by budget if user provided one.
    if max_budget is not None:
        filtered = [
            p for p in filtered if float(p.get("price", 0)) <= max_budget
        ]

    category_prices = [float(p.get("price", 0)) for p in filtered] if filtered else []

    # Sort by computed score in descending order.
    ranked = sorted(
        filtered,
        key=lambda p: score_product(
            p, max_budget=max_budget, category_prices=category_prices
        ),
        reverse=True,
    )

    top_items = ranked[:top_n]
    # Add debug score to product copies so main.py can print it.
    output: List[Dict[str, Any]] = []
    for item in top_items:
        item_copy = dict(item)
        item_copy["recommendationScore"] = round(
            score_product(item, max_budget=max_budget, category_prices=category_prices), 2
        )
        output.append(item_copy)

    return output, matched_category


def nearest_matching_products(
    products: List[Dict[str, Any]],
    user_input: str,
    max_budget: Optional[float] = None,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Return a helpful nearest list based on title/category fuzzy matching.
    """
    normalized_input = _normalize(user_input)
    if not normalized_input:
        return []

    candidate_products = products
    if max_budget is not None:
        candidate_products = [
            p for p in candidate_products if float(p.get("price", 0)) <= max_budget
        ]

    # Score candidates by text closeness + normal product score.
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for product in candidate_products:
        title = _normalize(str(product.get("title", "")))
        category = _normalize(str(product.get("category", "")))
        text_bonus = 0.0
        if normalized_input in category:
            text_bonus += 3.0
        if normalized_input in title:
            text_bonus += 2.0
        if get_close_matches(normalized_input, [category], n=1, cutoff=0.6):
            text_bonus += 1.5
        if get_close_matches(normalized_input, [title], n=1, cutoff=0.7):
            text_bonus += 1.0

        final_score = score_product(product) + text_bonus
        scored.append((final_score, product))

    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:top_n]]


def products_in_category(
    products: List[Dict[str, Any]], matched_category: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Return products from only the matched category.
    """
    if not matched_category:
        return []

    matched_normalized = _normalize(matched_category)
    return [
        p
        for p in products
        if _normalize(str(p.get("category", ""))) == matched_normalized
    ]


def budget_fallback_same_category(
    category_products: List[Dict[str, Any]],
    budget: float,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Return closest products from the same category when budget is too low.

    We sort by price distance from budget (closest first), then by score.
    """
    category_prices = [float(p.get("price", 0)) for p in category_products]
    scored: List[Tuple[float, float, Dict[str, Any]]] = []
    for product in category_products:
        price = float(product.get("price", 0))
        distance = abs(price - budget)
        # Negative score here because we want descending score as tiebreaker.
        scored.append(
            (
                distance,
                -score_product(
                    product,
                    max_budget=budget,
                    category_prices=category_prices,
                ),
                product,
            )
        )

    ranked = sorted(scored, key=lambda item: (item[0], item[1]))
    output: List[Dict[str, Any]] = []
    for _, _, product in ranked[:top_n]:
        product_copy = dict(product)
        product_copy["recommendationScore"] = round(
            score_product(
                product,
                max_budget=budget,
                category_prices=category_prices,
            ),
            2,
        )
        output.append(product_copy)
    return output


def category_budget_info(
    category_products: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
    """
    Return minimum price and a simple suggested budget range for a category.
    """
    if not category_products:
        return None, None

    prices = sorted(float(p.get("price", 0)) for p in category_products)
    min_price = prices[0]
    max_price = prices[-1]

    # Beginner-friendly suggested range: minimum up to category max.
    return min_price, (min_price, max_price)
