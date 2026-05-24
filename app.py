"""
Flask web UI for Smart Product Recommendation Agent.

This file only handles HTTP routes and HTML rendering. All product logic
lives in src.recommendation_service.run_recommendations (same pipeline as main.py).
"""

import os
from typing import List, Optional, Tuple

from flask import Flask, render_template, request

from src.llm_config import load_project_env

# Load project-root .env before Gemini-backed imports (same as console app).
load_project_env()

from src.api_dummyjson import fetch_categories
from src.recommendation_service import run_recommendations

# Flask app: templates/ and static/ are discovered from this file's folder by default.
app = Flask(__name__)


def _normalize_category_label(value: str) -> str:
    """Same idea as backend normalize — compare user text vs resolved category."""
    return (value or "").lower().strip().replace("-", " ").replace("_", " ")


def _load_categories_safe() -> Tuple[List[str], Optional[str]]:
    """
    Fetch category list from DummyJSON for the UI.
    Returns (list, error_message_or_none).
    """
    try:
        cats = fetch_categories()
        if isinstance(cats, list):
            return sorted(c for c in cats if isinstance(c, str) and c.strip()), None
        return [], "Unexpected category response from API."
    except Exception as exc:
        return [], f"Could not load categories: {exc}"


def _parse_budget(raw: str) -> Optional[float]:
    """Turn form budget string into float or None (no filter)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Single-page UI: show form on GET; on POST, run backend and show results.

    Categories are always loaded from DummyJSON so users can browse before searching.
    """
    all_categories, categories_error = _load_categories_safe()

    result = None
    category_value = ""
    budget_value = ""
    budget_error = None
    # True when backend resolved input to a different canonical category (fuzzy/alias).
    fuzzy_category_highlight = False

    if request.method == "POST":
        category_value = request.form.get("category", "").strip()
        budget_raw = request.form.get("budget", "")
        budget_value = budget_raw.strip()

        max_budget = _parse_budget(budget_raw)
        if budget_raw.strip() and max_budget is None:
            budget_error = "Budget must be a valid number, or leave blank."

        if budget_error is None:
            result = run_recommendations(
                category_input=category_value,
                max_budget=max_budget,
            )

            if result and result.get("success") and not result.get("error"):
                matched = result.get("matched_category")
                if matched and category_value:
                    fuzzy_category_highlight = _normalize_category_label(
                        category_value
                    ) != _normalize_category_label(str(matched))

    return render_template(
        "index.html",
        result=result,
        category_value=category_value,
        budget_value=budget_value,
        budget_error=budget_error,
        all_categories=all_categories,
        categories_error=categories_error,
        fuzzy_category_highlight=fuzzy_category_highlight,
    )


if __name__ == "__main__":
    # Beginner-friendly: run with `python app.py` from project root.
    # debug=True is convenient for learning; turn off in production.
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
