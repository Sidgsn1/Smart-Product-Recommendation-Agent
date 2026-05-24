"""
Shared recommendation pipeline for console (main.py) and web (app.py).

This module calls the same backend functions as the original main flow via the CrewAI
agent pipeline in crew_pipeline.py: DummyJSON fetch, scoring, fuzzy category matching,
Gemini summary, price history, alerts.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import logging

from src.crew_pipeline import execute_crew_pipeline
from src.recommendation import score_product

logger = logging.getLogger(__name__)


def _split_alert_types(products: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """
    Split stock vs discount alerts so the UI can show them in separate sections.
    Uses the same rules as build_alerts but returns two lists.
    """
    stock_alerts: List[str] = []
    discount_alerts: List[str] = []
    for product in products:
        title = str(product.get("title", "Unknown Product"))
        stock = int(product.get("stock", 0))
        discount = float(product.get("discountPercentage", 0))
        if stock < 10:
            stock_alerts.append(f"[Low Stock] {title} has only {stock} items left.")
        if discount >= 15:
            discount_alerts.append(
                f"[Great Deal] {title} has a {discount:.1f}% discount."
            )
    return stock_alerts, discount_alerts


def _ensure_scores(
    items: List[Dict[str, Any]],
    max_budget: Optional[float],
    all_products: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ensure each product has recommendationScore for display/sorting.
    nearest_matching_products may omit the score; compute it here when missing.
    """
    result: List[Dict[str, Any]] = []
    for item in items:
        copy_item = dict(item)
        if "recommendationScore" not in copy_item:
            cat = str(copy_item.get("category", ""))
            cat_prices = [
                float(p.get("price", 0))
                for p in all_products
                if str(p.get("category", "")) == cat
            ]
            if not cat_prices:
                cat_prices = [float(copy_item.get("price", 0))]
            copy_item["recommendationScore"] = round(
                score_product(copy_item, max_budget=max_budget, category_prices=cat_prices),
                2,
            )
        result.append(copy_item)
    return result


def _product_image_url(product: Dict[str, Any]) -> str:
    """
    DummyJSON provides `thumbnail` and often `images` (list of URLs).
    Prefer thumbnail for cards; fall back to first full image.
    """
    thumb = product.get("thumbnail")
    if isinstance(thumb, str) and thumb.strip():
        return thumb.strip()
    images = product.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return ""


def _serialize_product_for_display(
    product: Dict[str, Any],
    price_drop_ids: Set[str],
) -> Dict[str, Any]:
    """
    Build a plain dict for templates: prices, scores, image URL, and simple badge flags.
    Thresholds match existing alert logic (discount >= 15, stock < 10).
    """
    product_id = product.get("id")
    pid_str = str(product_id) if product_id is not None else ""
    rating = float(product.get("rating", 0))
    discount = float(product.get("discountPercentage", 0))
    stock = int(product.get("stock", 0))

    return {
        "id": product_id,
        "title": product.get("title", ""),
        "category": product.get("category", ""),
        "price": float(product.get("price", 0)),
        "rating": rating,
        "discountPercentage": discount,
        "recommendationScore": float(product.get("recommendationScore", 0)),
        "imageUrl": _product_image_url(product),
        "stock": stock,
        # Badge flags for the UI (beginner-friendly booleans in Jinja).
        "show_high_rating": rating >= 4.5,
        "show_best_deal": discount >= 15.0,
        "show_low_stock": stock < 10,
        "show_price_drop": bool(pid_str) and pid_str in price_drop_ids,
    }


def run_recommendations(
    category_input: str,
    max_budget: Optional[float],
) -> Dict[str, Any]:
    """
    Run the full recommendation pipeline once via the CrewAI agent workflow.

    Returns a dictionary used by Flask templates and optionally by the CLI.
    """
    out: Dict[str, Any] = {
        "success": False,
        "error": None,
        "recommendations": [],
        "matched_category": None,
        "info_messages": [],
        "stock_alerts": [],
        "discount_alerts": [],
        "price_alerts": [],
        "summary": "",
        "total_products": 0,
        "category_input": (category_input or "").strip(),
        "max_budget": max_budget,
    }

    logger.info("Starting recommendation pipeline")

    ctx = execute_crew_pipeline(
        category_input=category_input,
        max_budget=max_budget,
        ensure_scores_fn=_ensure_scores,
        split_alert_types_fn=_split_alert_types,
    )

    out["total_products"] = ctx.total_products
    out["matched_category"] = ctx.matched_category
    out["info_messages"] = ctx.info_messages

    if ctx.error:
        out["error"] = ctx.error
        return out

    out["success"] = True
    out["recommendations"] = [
        _serialize_product_for_display(p, ctx.price_drop_ids) for p in ctx.recommendations
    ]
    out["stock_alerts"] = ctx.stock_alerts
    out["discount_alerts"] = ctx.discount_alerts
    out["price_alerts"] = ctx.price_alerts
    out["summary"] = ctx.summary
    return out
