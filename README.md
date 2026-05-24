# Smart Product Recommendation Agent

A beginner-friendly Python console project that recommends products using the [DummyJSON Products API](https://dummyjson.com/products) and includes Gemini-powered AI summaries with fallback mode.

## Features

- Fetches all product data from DummyJSON (pagination)
- Lets you filter by category and budget
- Smart category matching (case-insensitive, partial, typo-friendly)
- Scores and ranks products with simple logic
- Shows useful alerts (low stock, high discount)
- Suggests closest category and nearest products when exact match is empty
- Optional Gemini-generated recommendation summary

## Project Structure

- `main.py` - Console entry point
- `requirements.txt` - Python dependencies
- `src/api_dummyjson.py` - API calls to DummyJSON
- `src/recommendation.py` - Recommendation filtering and scoring
- `src/alerts.py` - Alert generation for products
- `src/llm_config.py` - Shared Gemini config (LangChain + CrewAI) via `.env`
- `src/crew_pipeline.py` - CrewAI agent workflow (Manager → Search → Comparison → Alert → Summary)
- `src/crew_flow.py` - Gemini summary with LangChain fallback

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Gemini / CrewAI / LangChain

- Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (web app reads it on startup).
- Console `main.py` can also prompt for a key and save it to `.env`.
- Summaries use **CrewAI Gemini** (Summary Agent only) with **LangChain** as backup; other agents are deterministic (no Gemini calls).
- Optional: `GEMINI_MODEL=gemini-2.0-flash` in `.env`.
- If no key is set, the app still works with deterministic fallback summaries.

## Run web UI

```bash
python app.py
```

Open http://127.0.0.1:5000
