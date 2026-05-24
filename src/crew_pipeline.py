"""
CrewAI orchestration pipeline for Smart Product Recommendation Agent.

Workflow:
  User Input → Manager → Search → Comparison → Alert → Summary → Final Response

CrewAI Agent / Task / Crew objects define the workflow structure.
All business logic runs through existing Python modules (api, recommendation, alerts, crew_flow).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from crewai import Agent, Crew, Process, Task

from src.api_dummyjson import fetch_categories, fetch_products
from src.crew_flow import summarize_recommendations
from src.llm_config import get_crewai_llm, is_gemini_configured
from src.price_history import (
    build_current_price_map,
    detect_price_change_alerts,
    load_price_history,
    product_ids_with_price_drop,
    save_price_history,
)
from src.recommendation import (
    budget_fallback_same_category,
    category_budget_info,
    nearest_matching_products,
    products_in_category,
    recommend_products,
    suggest_closest_category,
)

logger = logging.getLogger(__name__)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@dataclass
class PipelineContext:
    """Shared state passed through each agent step."""

    category_input: str
    max_budget: Optional[float]
    categories: List[str] = field(default_factory=list)
    products: List[Dict[str, Any]] = field(default_factory=list)
    previous_prices: Dict[str, float] = field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    matched_category: Optional[str] = None
    info_messages: List[str] = field(default_factory=list)
    stock_alerts: List[str] = field(default_factory=list)
    discount_alerts: List[str] = field(default_factory=list)
    price_alerts: List[str] = field(default_factory=list)
    price_drop_ids: Set[str] = field(default_factory=set)
    summary: str = ""
    total_products: int = 0
    error: Optional[str] = None
    crew: Optional[Crew] = None


# ---------------------------------------------------------------------------
# Step executors — call existing business logic (no rewrites)
# ---------------------------------------------------------------------------


def run_manager_step(ctx: PipelineContext) -> str:
    """
    Manager Agent: validate user input and prepare the pipeline run.
    """
    logger.info(
        "Manager Agent: orchestrating workflow (category=%r, budget=%s)",
        ctx.category_input or "any",
        ctx.max_budget if ctx.max_budget is not None else "any",
    )
    if ctx.max_budget is not None and ctx.max_budget < 0:
        ctx.error = "Budget must be a positive number."
        return ctx.error

    return (
        f"Pipeline ready for category='{ctx.category_input or 'any'}' "
        f"and budget='{ctx.max_budget if ctx.max_budget is not None else 'any'}'."
    )


def run_search_step(ctx: PipelineContext) -> str:
    """
    Search Agent: fetch categories and products via DummyJSON helpers.
    Also loads and updates local price history.
    """
    logger.info("Search Agent: fetching categories and products")

    try:
        ctx.categories = fetch_categories()
    except Exception as exc:
        logger.warning("Search Agent: could not fetch categories (%s)", exc)
        ctx.categories = []

    try:
        ctx.products = fetch_products(limit=None)
    except Exception as exc:
        logger.exception("Search Agent: product fetch failed")
        ctx.error = f"Could not fetch products: {exc}"
        return ctx.error

    ctx.total_products = len(ctx.products)
    logger.info("Search Agent: fetched %d products", ctx.total_products)

    ctx.previous_prices = load_price_history()
    current_prices = build_current_price_map(ctx.products)
    save_price_history(current_prices)

    return f"Fetched {ctx.total_products} products and {len(ctx.categories)} categories."


def run_comparison_step(
    ctx: PipelineContext,
    ensure_scores_fn: Any,
) -> str:
    """
    Comparison Agent: rank and recommend products using existing scoring logic.
    """
    if ctx.error or not ctx.products:
        return "Skipped — no products available."

    logger.info("Comparison Agent: ranking products")

    recommendations, matched_category = recommend_products(
        products=ctx.products,
        category=ctx.category_input or None,
        max_budget=ctx.max_budget,
        top_n=5,
    )
    ctx.matched_category = matched_category

    if not recommendations:
        budget_fallback_mode = bool(matched_category and ctx.max_budget is not None)
        if budget_fallback_mode:
            same_category_products = products_in_category(ctx.products, matched_category)
            if same_category_products:
                min_price, suggested_range = category_budget_info(same_category_products)
                recommendations = budget_fallback_same_category(
                    category_products=same_category_products,
                    budget=ctx.max_budget,
                    top_n=5,
                )
                ctx.info_messages.append(
                    "No products found within your budget. "
                    "Showing closest products from the same category."
                )
                if min_price is not None:
                    ctx.info_messages.append(
                        f"Minimum available price in '{matched_category}': ${min_price:.2f}"
                    )
                if suggested_range is not None:
                    ctx.info_messages.append(
                        "Suggested budget range: "
                        f"${suggested_range[0]:.2f} - ${suggested_range[1]:.2f}"
                    )
            else:
                ctx.error = (
                    "No products found in the matched category data. "
                    "Try a different category."
                )
                return ctx.error
        else:
            ctx.info_messages.append("No direct matches found for your exact filters.")

        if not recommendations and not budget_fallback_mode:
            closest = suggest_closest_category(ctx.category_input, ctx.categories)
            if closest:
                ctx.info_messages.append(f"Closest category suggestion: {closest}")
            near = nearest_matching_products(
                products=ctx.products,
                user_input=ctx.category_input or "",
                max_budget=ctx.max_budget,
                top_n=5,
            )
            if near:
                recommendations = ensure_scores_fn(near, ctx.max_budget, ctx.products)
            else:
                ctx.error = (
                    "No nearest products found. Try removing category or budget filters."
                )
                return ctx.error

    if not recommendations:
        ctx.error = "No recommendations available for this query."
        return ctx.error

    recommendations = ensure_scores_fn(recommendations, ctx.max_budget, ctx.products)
    ctx.recommendations = sorted(
        recommendations,
        key=lambda p: float(p.get("recommendationScore", 0)),
        reverse=True,
    )

    logger.info(
        "Comparison Agent: selected %d recommendations (category=%r)",
        len(ctx.recommendations),
        ctx.matched_category,
    )
    return f"Ranked {len(ctx.recommendations)} recommended products."


def run_alert_step(
    ctx: PipelineContext,
    split_alert_types_fn: Any,
) -> str:
    """
    Alert Agent: generate stock, discount, and price-change alerts.
    """
    if ctx.error or not ctx.recommendations:
        return "Skipped — no recommendations to alert on."

    logger.info("Alert Agent: generating alerts")

    stock, discount = split_alert_types_fn(ctx.recommendations)
    ctx.stock_alerts = stock
    ctx.discount_alerts = discount
    ctx.price_alerts = detect_price_change_alerts(ctx.recommendations, ctx.previous_prices)
    ctx.price_drop_ids = product_ids_with_price_drop(ctx.recommendations, ctx.previous_prices)

    total = len(stock) + len(discount) + len(ctx.price_alerts)
    logger.info("Alert Agent: produced %d alert messages", total)
    return f"Generated {total} alerts."


def run_summary_step(ctx: PipelineContext) -> str:
    """
    Summary Agent: produce a Gemini-powered summary (with fallback).
    """
    if ctx.error or not ctx.recommendations:
        return "Skipped — no recommendations to summarize."

    logger.info(
        "Summary Agent: generating recommendation summary (only Gemini step in pipeline)"
    )

    user_goal = (
        f"Recommend products for category='{ctx.category_input or 'any'}' "
        f"and budget='{ctx.max_budget if ctx.max_budget is not None else 'any'}'."
    )
    ctx.summary = summarize_recommendations(ctx.recommendations, user_goal=user_goal)
    logger.info("Summary Agent: summary ready (%d chars)", len(ctx.summary))
    return "Summary generated."


# ---------------------------------------------------------------------------
# CrewAI Agent / Task / Crew definitions (orchestration structure)
# ---------------------------------------------------------------------------


def build_recommendation_crew(ctx: PipelineContext) -> Crew:
    """
    Build the full Agent → Task → Crew graph for the recommendation workflow.

    Gemini is attached only to the Summary Agent. Manager / Search / Comparison / Alert
    are deterministic (no LLM) — execution uses existing Python logic in step functions.
    """
    # Shared CrewAI Gemini singleton — used only by the Summary Agent (see crew_flow.py).
    summary_llm = get_crewai_llm()
    if is_gemini_configured() and summary_llm is None:
        logger.warning(
            "GEMINI_API_KEY is set but CrewAI LLM could not be initialized; "
            "summary will use LangChain or fallback."
        )

    # Manager orchestrates workflow only; no Gemini calls.
    manager_agent = Agent(
        role="Product Recommendation Manager",
        goal="Orchestrate search, comparison, alerts, and summary for the user request.",
        backstory=(
            "You lead a team of specialist agents that turn a category and budget "
            "into ranked product recommendations with alerts and a clear summary."
        ),
        verbose=False,
        allow_delegation=False,
    )

    # Deterministic agents — no LLM; steps call api_dummyjson / recommendation / alerts.
    search_agent = Agent(
        role="Product Search Specialist",
        goal="Fetch the full product catalog and category list from DummyJSON.",
        backstory=(
            "You retrieve fresh product data and keep price history up to date "
            "before any ranking happens."
        ),
        verbose=False,
        allow_delegation=False,
    )

    comparison_agent = Agent(
        role="Product Comparison Specialist",
        goal="Filter, score, and rank products that best match the user's preferences.",
        backstory=(
            "You apply the project's scoring and category-matching rules to surface "
            "the top product picks."
        ),
        verbose=False,
        allow_delegation=False,
    )

    alert_agent = Agent(
        role="Shopping Alert Specialist",
        goal="Flag low stock, great deals, and price changes on recommended products.",
        backstory=(
            "You watch stock levels, discounts, and price history so users never "
            "miss an important buying signal."
        ),
        verbose=False,
        allow_delegation=False,
    )

    summary_agent = Agent(
        role="Recommendation Summary Specialist",
        goal="Write a clear, beginner-friendly summary of the top product picks.",
        backstory=(
            "You explain why the recommended products are good choices using ratings, "
            "price value, and discount advantages."
        ),
        llm=summary_llm,
        verbose=False,
        allow_delegation=False,
    )

    category_label = ctx.category_input or "any"
    budget_label = ctx.max_budget if ctx.max_budget is not None else "any"

    manager_task = Task(
        description=(
            f"Review the user request: category='{category_label}', budget='{budget_label}'. "
            "Confirm the pipeline will run search → comparison → alerts → summary."
        ),
        expected_output="A brief confirmation that the workflow is ready.",
        agent=manager_agent,
    )

    search_task = Task(
        description=(
            "Fetch all products and categories from DummyJSON. "
            "Update local price history for price-change detection."
        ),
        expected_output="Count of products fetched and categories loaded.",
        agent=search_agent,
        context=[manager_task],
    )

    comparison_task = Task(
        description=(
            "Rank and recommend the top products for the user's category and budget. "
            "Apply fallback logic when exact matches are empty."
        ),
        expected_output="A ranked list of recommended products with scores.",
        agent=comparison_agent,
        context=[search_task],
    )

    alert_task = Task(
        description=(
            "Generate stock, discount, and price-change alerts for the recommended products."
        ),
        expected_output="Alert messages for stock, deals, and price changes.",
        agent=alert_agent,
        context=[comparison_task],
    )

    summary_task = Task(
        description=(
            "Write a natural-language summary explaining why the recommended products "
            "are good choices for the user."
        ),
        expected_output=(
            "A short recommendation summary with 2 paragraphs and 3 bullet points."
        ),
        agent=summary_agent,
        context=[alert_task],
    )

    crew = Crew(
        agents=[
            manager_agent,
            search_agent,
            comparison_agent,
            alert_agent,
            summary_agent,
        ],
        tasks=[manager_task, search_task, comparison_task, alert_task, summary_task],
        process=Process.sequential,
        verbose=False,
    )
    ctx.crew = crew
    return crew


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def execute_crew_pipeline(
    category_input: str,
    max_budget: Optional[float],
    *,
    ensure_scores_fn: Any = None,
    split_alert_types_fn: Any = None,
) -> PipelineContext:
    """
    Run the full agent pipeline and return populated context.

    CrewAI objects define the workflow; each step executes existing Python logic directly.
    """
    ctx = PipelineContext(
        category_input=(category_input or "").strip(),
        max_budget=max_budget,
    )

    build_recommendation_crew(ctx)
    logger.info("Crew assembled with %d agents", len(ctx.crew.agents) if ctx.crew else 0)

    # Sequential execution flow — each step maps to one specialist agent.
    steps: List[Tuple[str, Any]] = [
        ("Manager Agent", lambda: run_manager_step(ctx)),
        ("Search Agent", lambda: run_search_step(ctx)),
    ]

    if ensure_scores_fn is not None:
        steps.append(
            (
                "Comparison Agent",
                lambda: run_comparison_step(ctx, ensure_scores_fn),
            )
        )
    if split_alert_types_fn is not None:
        steps.append(
            ("Alert Agent", lambda: run_alert_step(ctx, split_alert_types_fn))
        )

    steps.append(("Summary Agent", lambda: run_summary_step(ctx)))

    for step_name, step_fn in steps:
        if ctx.error:
            logger.warning("%s: skipped (pipeline halted)", step_name)
            break
        try:
            logger.info("--- %s: starting ---", step_name)
            step_fn()
            logger.info("--- %s: done ---", step_name)
        except Exception as exc:
            logger.exception("%s: failed", step_name)
            ctx.error = f"{step_name} failed: {exc}"
            break

    if ctx.error:
        logger.error("Pipeline finished with error: %s", ctx.error)
    else:
        logger.info("Pipeline finished successfully")

    return ctx
