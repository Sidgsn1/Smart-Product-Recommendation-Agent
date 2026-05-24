# Smart Product Recommendation Agent

A hybrid multi-agent product recommendation system built with Python, Flask, CrewAI, LangChain, and Gemini API.

The project fetches products from the DummyJSON Products API, ranks them using deterministic recommendation algorithms, generates alerts, and optionally produces AI-powered recommendation summaries using Gemini.

---

## Features

* Product search using DummyJSON API
* Budget-based filtering
* Smart category matching
* Deterministic product scoring and ranking
* Price-drop, stock, and discount alerts
* CrewAI-based multi-agent workflow
* Gemini-powered recommendation summaries
* LangChain Gemini integration
* Flask web UI + CLI support
* Deterministic fallback summaries when Gemini quota is unavailable

---

## Multi-Agent Architecture

The system uses a hybrid CrewAI orchestration model with 5 specialized agents:

| Agent            | Responsibility                        |
| ---------------- | ------------------------------------- |
| Manager Agent    | Controls workflow orchestration       |
| Search Agent     | Fetches and filters products          |
| Comparison Agent | Ranks and scores products             |
| Alert Agent      | Generates stock/discount/price alerts |
| Summary Agent    | Generates Gemini-powered summaries    |

Most agents use deterministic Python logic for speed, accuracy, and explainability.
Only the Summary Agent uses Gemini AI for natural-language recommendation summaries.

---

## Tech Stack

### Backend

* Python
* Flask

### AI / Multi-Agent

* CrewAI
* LangChain
* Google Gemini API

### Frontend

* HTML
* CSS
* JavaScript

### APIs

* DummyJSON Products API

---

## Project Structure

```text
SmartProductAgent/
├── app.py
├── main.py
├── requirements.txt
├── src/
│   ├── api_dummyjson.py
│   ├── recommendation.py
│   ├── alerts.py
│   ├── price_history.py
│   ├── recommendation_service.py
│   ├── crew_pipeline.py
│   ├── crew_flow.py
│   └── llm_config.py
├── templates/
├── static/
└── .env.example
```

---

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/SmartProductAgent.git
cd SmartProductAgent
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate Virtual Environment

#### Git Bash

```bash
source .venv/Scripts/activate
```

#### PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Gemini API Setup

Copy:

```bash
cp .env.example .env
```

Then add your Gemini API key:

```env
GEMINI_API_KEY=your_key_here
```

Optional:

```env
GEMINI_MODEL=gemini-2.0-flash
```

If no Gemini key is provided, the application still works using deterministic fallback summaries.

---

## Run Flask Web App

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## Run CLI Version

```bash
python main.py
```

---

## Architecture Workflow

```text
User Input
   ↓
Manager Agent
   ↓
Search Agent
   ↓
Comparison Agent
   ↓
Alert Agent
   ↓
Summary Agent (Gemini)
   ↓
Final Response
```

---

## Key Design Decisions

* Deterministic Python logic is used for:

  * filtering
  * scoring
  * ranking
  * alerts
  * price tracking

* Gemini AI is used only for:

  * natural-language recommendation summaries

This hybrid architecture reduces API cost, improves reliability, and avoids unnecessary AI usage for mathematical operations.

---

## Future Improvements

* Database integration
* Real-time product APIs
* User accounts and history
* Email alerts
* Advanced recommendation algorithms
* Docker deployment

---
