"""Alert helpers for recommended products."""

from typing import Any, Dict, List


def build_alerts(products: List[Dict[str, Any]]) -> List[str]:
    """
    Build simple alert messages for each product.

    Alerts include:
    - Low stock warning
    - High discount callout
    """
    alert_messages: List[str] = []

    for product in products:
        title = str(product.get("title", "Unknown Product"))
        stock = int(product.get("stock", 0))
        discount = float(product.get("discountPercentage", 0))

        if stock < 10:
            alert_messages.append(f"[Low Stock] {title} has only {stock} items left.")
        if discount >= 15:
            alert_messages.append(
                f"[Great Deal] {title} has a {discount:.1f}% discount."
            )

    return alert_messages
