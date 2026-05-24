"""
Recommendation summary via CrewAI + LangChain Gemini, with deterministic fallback.

Only this module invokes Gemini. Other agents use deterministic Python logic.
"""

import logging
from typing import Any, Dict, List, Optional

from src.llm_config import get_crewai_llm, get_gemini_llm, is_gemini_configured

logger = logging.getLogger(__name__)


def _fallback_summary(products: List[Dict[str, Any]], user_goal: str) -> str:
    """
    Simple text summary when Gemini / CrewAI cannot run.
    """
    if not products:
        return "No products found for your preferences."

    lines = [f"Goal: {user_goal}", "Top recommendations:"]
    for index, product in enumerate(products, start=1):
        lines.append(
            f"{index}. {product.get('title')} - ${product.get('price')} "
            f"(Rating: {product.get('rating')}, Discount: {product.get('discountPercentage')}%)"
        )
    return "\n".join(lines)


def _format_product_lines(products: List[Dict[str, Any]]) -> str:
    """Build a compact product list for LLM prompts."""
    product_lines = []
    for p in products:
        product_lines.append(
            f"- {p.get('title')} | category={p.get('category')} | "
            f"price=${p.get('price')} | rating={p.get('rating')} | "
            f"discount={p.get('discountPercentage')}%"
        )
    return "\n".join(product_lines)


def _build_summary_prompt(user_goal: str, product_lines: str) -> str:
    """Shared instructions for CrewAI task and LangChain invoke."""
    return (
        "You are a helpful shopping recommendation assistant.\n"
        "Write a natural, friendly summary for a beginner user.\n"
        "Explain WHY the products are good choices.\n"
        "Mention rating, price value, and discount advantages clearly.\n"
        "Keep it short: 2 short paragraphs plus 3 bullet points.\n"
        "Do not repeat raw data mechanically.\n\n"
        f"User goal:\n{user_goal}\n\n"
        f"Recommended products:\n{product_lines}"
    )


def _is_quota_exhausted(exc: BaseException) -> bool:
    """True when Gemini quota/rate limit is hit — skip redundant LangChain retries."""
    message = str(exc).upper()
    return "429" in message or "RESOURCE_EXHAUSTED" in message or "QUOTA" in message


def _summarize_with_crewai(prompt: str) -> tuple[Optional[str], bool]:
    """
    Call the shared CrewAI Gemini LLM once (no nested crew kickoff / agent loop).

    Returns (summary_text, quota_exhausted). Uses the same singleton as the Summary Agent.
    """
    llm = get_crewai_llm()
    if llm is None:
        return None, False

    try:
        result = llm.call(prompt)
        text = str(result).strip()
        if text:
            logger.info("Summary generated via CrewAI Gemini (single call)")
            return text, False
        return None, False
    except Exception as exc:
        quota = _is_quota_exhausted(exc)
        logger.warning("CrewAI Gemini summary failed: %s", exc)
        return None, quota


def _summarize_with_langchain(prompt: str) -> Optional[str]:
    """
    Fallback path: call the shared LangChain ChatGoogleGenerativeAI directly.
    """
    llm = get_gemini_llm()
    if llm is None:
        return None

    try:
        from langchain_core.messages import HumanMessage

        response = llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", "") or ""
        text = str(content).strip()
        if text:
            logger.info("Summary generated via LangChain Gemini")
            return text
        return None
    except Exception as exc:
        logger.warning("LangChain Gemini summary failed: %s", exc)
        return None


def summarize_recommendations(products: List[Dict[str, Any]], user_goal: str) -> str:
    """
    Generate an AI summary with CrewAI (primary), LangChain Gemini (secondary),
    then deterministic fallback if keys or APIs are unavailable.
    """
    if not products:
        return "No products found for your preferences."

    if not is_gemini_configured():
        logger.info("GEMINI_API_KEY not set; using deterministic summary fallback")
        return _fallback_summary(products, user_goal)

    prompt = _build_summary_prompt(user_goal, _format_product_lines(products))

    # 1) CrewAI shared Gemini LLM (one direct call — no nested crew kickoff)
    summary, quota_exhausted = _summarize_with_crewai(prompt)
    if summary:
        return summary

    if quota_exhausted:
        logger.info(
            "Gemini quota exhausted; skipping LangChain retry, using deterministic fallback"
        )
        return _fallback_summary(products, user_goal)

    # 2) LangChain invoke with the same shared Gemini config
    summary = _summarize_with_langchain(prompt)
    if summary:
        return summary

    # 3) No API / network / SDK — safe default
    logger.info("Using deterministic summary fallback after Gemini paths failed")
    return _fallback_summary(products, user_goal)
