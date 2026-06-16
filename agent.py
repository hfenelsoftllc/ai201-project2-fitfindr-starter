"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex. Removes matched fragments from the text so the remaining
    words become the description passed to search_listings.
    """
    text = query

    # Extract price ceiling — matches "under $30", "under 30", "less than $40",
    # "max $25", "$50 or less"
    max_price = None
    price_patterns = [
        r"under\s+\$?(\d+(?:\.\d+)?)",
        r"less\s+than\s+\$?(\d+(?:\.\d+)?)",
        r"max(?:imum)?\s+\$?(\d+(?:\.\d+)?)",
        r"\$?(\d+(?:\.\d+)?)\s+or\s+less",
    ]
    for pattern in price_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            max_price = float(m.group(1))
            text = text[: m.start()] + " " + text[m.end() :]
            break

    # Extract size — matches "size M", "size 8", "in size XL", "in M"
    size = None
    size_patterns = [
        r"(?:in\s+)?size\s+([A-Za-z0-9/]+)",
        r"\bin\s+([SMLXsmlx]{1,3})\b",
    ]
    for pattern in size_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            size = m.group(1)
            text = text[: m.start()] + " " + text[m.end() :]
            break

    description = re.sub(r"\s+", " ", text).strip()
    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search listings — early exit if nothing matches
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        session["error"] = (
            "No listings found matching your search. "
            "Try broadening your description, adjusting the price ceiling, "
            "or removing the size filter."
        )
        return session

    # Step 4: select top result (highest relevance score)
    session["selected_item"] = results[0]

    # Step 5: suggest outfit combinations
    session["outfit_suggestion"] = suggest_outfit(results[0], wardrobe)

    # Step 6: generate shareable fit card caption
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
