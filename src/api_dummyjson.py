"""API helper functions for DummyJSON products."""

from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://dummyjson.com/products"


def _fetch_products_page(limit: int, skip: int) -> Dict[str, Any]:
    """
    Fetch a single paginated response from DummyJSON.
    """
    response = requests.get(BASE_URL, params={"limit": limit, "skip": skip}, timeout=20)
    response.raise_for_status()
    return response.json()


def fetch_products(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch products from DummyJSON.

    Args:
        limit: Maximum number of products to fetch.
               If None, fetches all available products.

    Returns:
        A list of product dictionaries.
    """
    # If caller provides a limit, do a single request for simplicity.
    if limit is not None:
        page = _fetch_products_page(limit=limit, skip=0)
        return page.get("products", [])

    # Fetch all products page by page so every category is represented.
    page_size = 100
    first_page = _fetch_products_page(limit=page_size, skip=0)
    all_products = list(first_page.get("products", []))
    total = int(first_page.get("total", len(all_products)))

    skip = page_size
    while len(all_products) < total:
        page = _fetch_products_page(limit=page_size, skip=skip)
        page_products = page.get("products", [])
        if not page_products:
            break
        all_products.extend(page_products)
        skip += page_size

    # Remove duplicates by id, just in case an API page overlaps.
    unique_by_id: Dict[Any, Dict[str, Any]] = {}
    for product in all_products:
        unique_by_id[product.get("id")] = product
    return list(unique_by_id.values())


def fetch_categories() -> List[str]:
    """
    Fetch available product categories from DummyJSON.
    """
    response = requests.get(f"{BASE_URL}/category-list", timeout=20)
    response.raise_for_status()
    categories = response.json()
    return categories if isinstance(categories, list) else []
