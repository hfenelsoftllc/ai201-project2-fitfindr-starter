# FitFindr

An AI-powered thrift shopping assistant that takes a natural language query, searches a secondhand listings dataset for the best match, suggests outfit combinations using the user's existing wardrobe, and generates a shareable Instagram/TikTok caption for the find.

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tests/
│   ├── conftest.py            # Adds project root to sys.path for pytest
│   └── test_tools.py          # 14 unit tests covering all three tools
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── agent.py                   # run_agent() planning loop
├── app.py                     # Gradio UI
├── planning.md                # Architecture, decisions, and AI tool plan
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Open the localhost URL shown in your terminal (usually `http://localhost:7860`). Type a query like `"vintage graphic tee under $30"`, pick a wardrobe, and hit **Find it**.

## Running Tests

```bash
pytest tests/test_tools.py -v
```

All 14 tests run without a live API key — LLM calls in `suggest_outfit` and `create_fit_card` are mocked.

## How It Works

User input flows through a linear planning loop in `agent.py`:

1. **Parse** — regex extracts `description`, `size`, and `max_price` from the query.
2. **Search** (`search_listings`) — filters the 40 listings by price and size, scores the remainder by keyword overlap across title, description, style tags, colors, and category, and returns results sorted by relevance.
3. **Outfit** (`suggest_outfit`) — sends the top listing and the user's wardrobe to `llama-3.3-70b-versatile` via Groq. If the wardrobe is empty, returns general styling advice instead.
4. **Fit card** (`create_fit_card`) — generates a 2–4 sentence OOTD caption (temperature 0.9) that naturally weaves in the item name, price, and platform.

If search returns no results the agent exits early with a user-friendly error message; the other two tools are never called.

## Data

`data/listings.json` — 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear). Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

`data/wardrobe_schema.json` — wardrobe format used by `suggest_outfit`, including an `example_wardrobe` (10 items) and an `empty_wardrobe` template.

```python
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings
```
