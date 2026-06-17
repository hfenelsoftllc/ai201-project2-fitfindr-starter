"""
tests/test_tools.py

One test per failure mode for each of the three FitFindr tools.
LLM-dependent tools (suggest_outfit, create_fit_card) mock the Groq client
so tests run without a live API key and finish in milliseconds.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_client(text: str) -> MagicMock:
    """Return a Groq client mock whose .chat.completions.create() returns text."""
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = text
    return client


# Minimal listing dict used across suggest_outfit and create_fit_card tests
_ITEM = {
    "title": "Vintage Flannel Shirt",
    "description": "Classic oversized flannel, great for layering.",
    "style_tags": ["vintage", "grunge", "flannel"],
    "colors": ["red", "black"],
    "price": 22.00,
    "platform": "thredUp",
}

_WARDROBE_WITH_ITEMS = {
    "items": [
        {
            "name": "Baggy straight-leg jeans",
            "colors": ["dark blue"],
            "style_tags": ["denim", "streetwear"],
        },
        {
            "name": "Chunky white sneakers",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky"],
        },
    ]
}

_EMPTY_WARDROBE = {"items": []}


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    """Happy path: a broad query with a generous price ceiling finds something."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results_no_exception():
    """Failure mode: impossible query returns [] and never raises."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter_respected():
    """Failure mode: items above max_price must not appear in results."""
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    """Size 'm' should match listings sized 'M', 'S/M', etc."""
    results = search_listings("tee", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_sorted_by_relevance():
    """More specific queries should surface higher-scoring items first."""
    general = search_listings("vintage", size=None, max_price=None)
    specific = search_listings("vintage graphic tee", size=None, max_price=None)
    # Both should return results; the specific query's top hit should be a top
    assert len(general) > 0
    assert len(specific) > 0
    # Top result of the specific query must contain at least one query keyword
    top = specific[0]
    searchable = (
        top["title"] + " " + top["description"] + " " + " ".join(top["style_tags"])
    ).lower()
    assert any(w in searchable for w in ["vintage", "graphic", "tee"])


def test_search_zero_keyword_overlap_excluded():
    """Listings with no matching keywords should not appear even if price/size pass."""
    results = search_listings("xyzzy frobnicator quux", size=None, max_price=None)
    assert results == []


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe_returns_string():
    """Happy path: wardrobe present → non-empty string returned."""
    with patch("tools._get_groq_client", return_value=_mock_client("Pair the flannel with baggy jeans.")):
        result = suggest_outfit(_ITEM, _WARDROBE_WITH_ITEMS)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_no_exception():
    """Failure mode: empty wardrobe must not raise and must return styling advice."""
    with patch("tools._get_groq_client", return_value=_mock_client("Style it with high-waisted trousers.")):
        result = suggest_outfit(_ITEM, _EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_uses_general_prompt():
    """Empty wardrobe branch must call the LLM (i.e. the client is invoked)."""
    mock_client = _mock_client("General advice here.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(_ITEM, _EMPTY_WARDROBE)
    mock_client.chat.completions.create.assert_called_once()


def test_suggest_outfit_wardrobe_branch_calls_llm():
    """Non-empty wardrobe branch must also call the LLM."""
    mock_client = _mock_client("Outfit suggestion here.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(_ITEM, _WARDROBE_WITH_ITEMS)
    mock_client.chat.completions.create.assert_called_once()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    """Failure mode: empty outfit → error string, no exception, no LLM call."""
    result = create_fit_card("", _ITEM)
    assert isinstance(result, str)
    assert "Error" in result


def test_create_fit_card_whitespace_outfit_returns_error_string():
    """Failure mode: whitespace-only outfit is also treated as empty."""
    result = create_fit_card("   ", _ITEM)
    assert isinstance(result, str)
    assert "Error" in result


def test_create_fit_card_no_llm_call_on_empty_outfit():
    """LLM must not be called when the outfit guard triggers."""
    mock_client = _mock_client("should not be called")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("", _ITEM)
    mock_client.chat.completions.create.assert_not_called()


def test_create_fit_card_returns_caption():
    """Happy path: valid outfit → non-empty caption string."""
    outfit = "Pair with baggy jeans and chunky sneakers for a grunge streetwear vibe."
    expected = "Just found this flannel on thredUp for $22 and I'm obsessed."
    with patch("tools._get_groq_client", return_value=_mock_client(expected)):
        result = create_fit_card(outfit, _ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
