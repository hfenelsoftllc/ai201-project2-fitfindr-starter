# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for thrift items that match a user's keyword description, optional size filter, and optional price ceiling. Returns a ranked list of matching listing dicts sorted by relevance score (best match first).

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Used to score listings by keyword overlap across title, description, style_tags, colors, and category fields.
- `size` (str | None): Size string to filter by, or None to skip. Case-insensitive substring match — "M" matches "S/M", "XL (oversized)", etc.
- `max_price` (float | None): Maximum price inclusive, or None to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score descending. Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a helpful message (e.g., "No listings found matching your description and filters — try broadening your search.") and returns early. `suggest_outfit` and `create_fit_card` are not called.

---

### Tool 2: suggest_outfit

**What it does:**
Calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations using the candidate thrift item and the user's existing wardrobe. If the wardrobe is empty, it returns general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): A listing dict for the item the user is considering buying. Uses `title`, `description`, `style_tags`, and `colors` fields to describe the item to the LLM.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts (each with `name`, `colors`, `style_tags`). May be empty — handled gracefully.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. If the wardrobe is empty, the string contains general styling ideas (aesthetic, silhouette pairings, color advice). If the wardrobe has items, the suggestions name specific wardrobe pieces.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool switches to a general-advice prompt rather than crashing. The LLM always returns a non-empty response, so no special fallback is needed beyond the empty-wardrobe branch.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM (llama-3.3-70b-versatile, temperature 0.9) to generate a 2–4 sentence Instagram/TikTok OOTD caption for the thrifted find. Naturally weaves in the item name, price, and platform once each.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()`. Used to ground the caption's vibe and styling details.
- `new_item` (dict): The listing dict for the thrifted item. Used to pull `title`, `price`, and `platform` for the caption.

**What it returns:**
A 2–4 sentence caption string suitable for social media. Casual and authentic in tone — not a product description. If `outfit` is empty or whitespace-only, returns the error string `"Error: outfit suggestion is missing or incomplete — cannot generate a fit card."` and does NOT raise an exception.

**What happens if it fails or returns nothing:**
An empty/whitespace `outfit` argument is caught before the LLM call and returns an error string. This protects against being called with bad state from earlier in the pipeline.

---

### Additional Tools (if any)

None beyond the three required tools.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent follows a fixed linear sequence — there is no branching decision beyond error guards:

1. Parse the user's query with a regex + keyword scan to extract `description`, `size`, and `max_price`.
2. Call `search_listings(description, size, max_price)`. If results are empty → set error, return early.
3. Select `search_results[0]` as the `selected_item` (highest relevance score).
4. Call `suggest_outfit(selected_item, wardrobe)`. Store result in `outfit_suggestion`.
5. Call `create_fit_card(outfit_suggestion, selected_item)`. Store result in `fit_card`.
6. Return the completed session dict.

The agent knows it's done when `fit_card` is populated (happy path) or `error` is set (early termination after empty search results).

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single session dict initialized by `_new_session(query, wardrobe)`. Each step writes its output into a named key before the next step reads it:

| Key | Written by | Read by |
|-----|-----------|---------|
| `query` | `_new_session` | query parser |
| `parsed` | query parser | `search_listings` call |
| `search_results` | `search_listings` | item selector |
| `selected_item` | item selector | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `_new_session` | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | returned to caller |
| `error` | early-termination guard | returned to caller |

No tool modifies any key it doesn't own. The session dict is the only shared state — there are no global variables or side-channel passes between tools.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (empty list returned) | Agent sets `session["error"]` to a user-friendly message and returns the session early. `suggest_outfit` and `create_fit_card` are never called with empty input. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"]` is `[]`) | Tool switches to a general styling advice prompt instead of a wardrobe-based prompt. Always returns a non-empty string — no exception, no empty output. |
| create_fit_card | Outfit input is empty or whitespace-only | Tool returns an error string immediately without calling the LLM. No exception is raised so the caller can display the error message directly. |

---

## Architecture

```
User input (query, wardrobe)
        │
        ▼
┌─────────────────────────┐
│   run_agent()           │
│   Planning Loop         │
│                         │
│  1. Parse query         │──► session["parsed"]
│         │               │
│  2. search_listings()   │──► session["search_results"]
│         │               │
│   [empty?] ──► ERROR ──►│──► session["error"] → return early
│         │               │
│  3. Select top item     │──► session["selected_item"]
│         │               │
│  4. suggest_outfit()    │──► session["outfit_suggestion"]
│         │               │
│  5. create_fit_card()   │──► session["fit_card"]
│         │               │
│  6. Return session      │
└─────────────────────────┘
        │
        ▼
  session dict
  ├── fit_card  (happy path)
  └── error     (early termination)
```

**Data flow between tools:**
- `search_listings` → returns list; `[0]` becomes `selected_item`
- `selected_item` + `wardrobe` → fed into `suggest_outfit`
- `suggest_outfit` result + `selected_item` → fed into `create_fit_card`
- `create_fit_card` result → displayed in Gradio UI via `app.py`

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

Used Claude (Claude Code) to implement all three tools in `tools.py`.

- **Input given:** The full `tools.py` stub with TODO comments, the `data_loader.py` utility, a sample from `listings.json`, and `wardrobe_schema.json` to understand field shapes. Alignment was done on: Groq model (`llama-3.3-70b-versatile`), scoring fields (all text fields), and prompt strategy (Option A: full wardrobe list sent to LLM).
- **What it produced:** Complete implementations of `search_listings` (regex tokenization + multi-field keyword scoring), `suggest_outfit` (empty-wardrobe branch + wardrobe-aware branch), and `create_fit_card` (empty-guard + high-temperature caption prompt).
- **Verification plan:** Run `python tools.py` (or pytest) with three scenarios — (1) a query that returns results, (2) a query with no matches, (3) `suggest_outfit` called with an empty wardrobe — and confirm correct behavior before wiring into `agent.py`.

**Milestone 4 — Planning loop and state management:**

Will use Claude (Claude Code) to implement `run_agent()` in `agent.py`.

- **Input:** This planning.md (Planning Loop + State Management + Architecture sections) plus the completed `tools.py`.
- **Expected output:** A working `run_agent()` that initializes the session, parses the query, calls the three tools in order, handles the empty-results early exit, and returns the completed session dict.
- **Verification:** Run `python agent.py` directly (it has a built-in CLI test for happy path and no-results path) and confirm both branches produce the expected output.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** The agent parses the query. It extracts `description = "vintage graphic tee"`, `max_price = 30.0`, `size = None` (no size mentioned). These go into `session["parsed"]`.

**Step 2:** `search_listings("vintage graphic tee", size=None, max_price=30.0)` is called. All listings are loaded, filtered to price ≤ $30, then scored by keyword overlap. Words "vintage", "graphic", "tee" are matched against title, description, style_tags, colors, and category for each listing. Results are sorted by score. The top match (e.g., "Y2K Baby Tee — Butterfly Print" at $18, tagged `["y2k", "vintage", "graphic tee"]`) is returned first.

**Step 3:** `selected_item = search_results[0]` — the Y2K Baby Tee. `suggest_outfit(selected_item, wardrobe)` is called. The wardrobe has 10 items (baggy jeans, chunky white sneakers, etc.), so the wardrobe-aware prompt is used. The LLM returns a suggestion naming specific pieces: e.g., "Pair the Y2K Baby Tee with the baggy straight-leg jeans and chunky white sneakers for a nostalgic streetwear look. Layer the black cropped zip hoodie for cooler weather." This goes into `session["outfit_suggestion"]`.

**Step 4:** `create_fit_card(outfit_suggestion, selected_item)` is called. The LLM generates a casual caption at temperature 0.9 — e.g., "Finally found my dream piece — snagged this Y2K Baby Tee on Depop for $18 and I can't stop wearing it. Styled it with baggy jeans and my go-to chunky sneakers for that early 2000s vibe I've been chasing all summer."

**Final output to user:**
The Gradio UI displays:
- The top search result (item title, price, platform, condition)
- The outfit suggestion paragraph naming their wardrobe pieces
- The fit card caption ready to copy-paste
