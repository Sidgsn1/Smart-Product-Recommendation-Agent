"""Console app entrypoint for Smart Product Recommendation Agent."""

from pathlib import Path
from typing import Optional

from src.llm_config import load_project_env, reset_gemini_llm_cache

# Load project-root .env before any Gemini-backed imports.
load_project_env()

from src.api_dummyjson import fetch_categories
from src.recommendation_service import run_recommendations


def _read_optional_budget() -> Optional[float]:
    """
    Read budget from user input.
    Returns None if the user leaves it empty.
    """
    raw_value = input("Enter max budget (or press Enter to skip): ").strip()
    if not raw_value:
        return None

    try:
        return float(raw_value)
    except ValueError:
        print("Invalid budget value. Ignoring budget filter.")
        return None


def _save_env_key(key_name: str, key_value: str) -> None:
    """
    Save or update one key in local .env file.
    """
    env_path = Path(".env")
    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines = []
    for line in existing_lines:
        if line.startswith(f"{key_name}="):
            new_lines.append(f"{key_name}={key_value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{key_name}={key_value}")

    env_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")


def _maybe_configure_gemini_api_key() -> None:
    """
    Ask user for Gemini API key and save it in .env if provided.
    """
    import os

    existing = os.getenv("GEMINI_API_KEY")
    if existing:
        print("Gemini API key already available from environment/.env.")
        return

    print("\nGemini setup (optional):")
    print("Paste your Gemini API key to enable AI summaries.")
    print("Or press Enter to skip and use fallback summary mode.")
    key = input("GEMINI_API_KEY: ").strip()
    if not key:
        print("Gemini key not provided. Fallback summary mode will be used.")
        return

    _save_env_key("GEMINI_API_KEY", key)
    # Also set it for the current process so this run can use Gemini immediately.
    os.environ["GEMINI_API_KEY"] = key
    reset_gemini_llm_cache()
    print("Gemini API key saved to .env successfully.")


def main() -> None:
    print("\n=== Smart Product Recommendation Agent ===\n")

    try:
        categories = fetch_categories()
        print("Available categories (first 15):")
        for category in categories[:15]:
            print(f"- {category}")
    except Exception as error:
        print(f"Warning: Could not fetch categories. ({error})")

    category_input = input("\nEnter category (or press Enter to skip): ").strip()
    max_budget = _read_optional_budget()
    _maybe_configure_gemini_api_key()

    print("\nFetching products and computing recommendations...")
    result = run_recommendations(category_input=category_input, max_budget=max_budget)

    if result.get("error"):
        print(f"\nError: {result['error']}")
        return

    print(f"Debug: Total fetched products = {result.get('total_products', 0)}")
    print(f"Debug: Matched category = {result.get('matched_category') or 'None'}")

    for msg in result.get("info_messages", []):
        print(f"\n{msg}")

    print("\nTop Recommended Products:")
    for index, product in enumerate(result.get("recommendations", []), start=1):
        print(
            f"{index}. {product.get('title')} | "
            f"Category: {product.get('category')} | "
            f"Price: ${product.get('price')} | "
            f"Rating: {product.get('rating')} | "
            f"Discount: {product.get('discountPercentage')}% | "
            f"Score: {product.get('recommendationScore', 'N/A')}"
        )

    stock = result.get("stock_alerts", [])
    discount = result.get("discount_alerts", [])
    if stock or discount:
        print("\nAlerts:")
        for alert in stock + discount:
            print(f"- {alert}")

    price_alerts = result.get("price_alerts", [])
    if price_alerts:
        print("\nPrice Change Alerts:")
        for alert in price_alerts:
            print(f"- {alert}")

    print("\nRecommendation Summary:")
    print(result.get("summary", ""))


if __name__ == "__main__":
    main()
