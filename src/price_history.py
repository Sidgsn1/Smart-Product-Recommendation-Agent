"""Simple local price history tracking using a JSON file."""

import json
from pathlib import Path
from typing import Any, Dict, List, Set


PRICE_HISTORY_FILE = Path("price_history.json")


def load_price_history() -> Dict[str, float]:
    """
    Load previous product prices from local JSON file.
    Returns an empty dictionary if the file does not exist.
    """
    if not PRICE_HISTORY_FILE.exists():
        return {}

    try:
        data = json.loads(PRICE_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # Keep only numeric values.
            return {
                str(product_id): float(price)
                for product_id, price in data.items()
                if isinstance(price, (int, float))
            }
    except Exception:
        # If file is malformed, start fresh.
        return {}
    return {}


def build_current_price_map(products: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Convert products list into {product_id: price}.
    """
    price_map: Dict[str, float] = {}
    for product in products:
        product_id = product.get("id")
        if product_id is None:
            continue
        price_map[str(product_id)] = float(product.get("price", 0))
    return price_map


def save_price_history(price_map: Dict[str, float]) -> None:
    """
    Save latest prices to local JSON file.
    """
    PRICE_HISTORY_FILE.write_text(
        json.dumps(price_map, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def detect_price_change_alerts(
    products: List[Dict[str, Any]],
    previous_prices: Dict[str, float],
) -> List[str]:
    """
    Build user-friendly price change alerts for given products.
    """
    alerts: List[str] = []

    for product in products:
        product_id = product.get("id")
        if product_id is None:
            continue

        key = str(product_id)
        if key not in previous_prices:
            continue

        old_price = float(previous_prices[key])
        new_price = float(product.get("price", 0))
        title = str(product.get("title", "Unknown Product"))

        if new_price < old_price:
            alerts.append(f"[Price Drop] {title}: Price dropped from ${old_price:.2f} to ${new_price:.2f}")
        elif new_price > old_price:
            alerts.append(f"[Price Increase] {title}: Price increased from ${old_price:.2f} to ${new_price:.2f}")

    return alerts


def product_ids_with_price_drop(
    products: List[Dict[str, Any]],
    previous_prices: Dict[str, float],
) -> Set[str]:
    """
    Return product id strings where current price is lower than the last saved price.
    Used by the web UI for per-card "Price Drop" badges (same rules as price alerts).
    """
    dropped: Set[str] = set()
    for product in products:
        product_id = product.get("id")
        if product_id is None:
            continue
        key = str(product_id)
        if key not in previous_prices:
            continue
        old_price = float(previous_prices[key])
        new_price = float(product.get("price", 0))
        if new_price < old_price:
            dropped.add(key)
    return dropped
