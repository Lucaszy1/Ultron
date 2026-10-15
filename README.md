# Ultron

An AI-assisted bookkeeping helper for a QuickBooks-based inventory business. It
pairs a Claude-powered chat assistant with a set of spreadsheet tools that parse,
validate, and reconcile the messy Excel/CSV exports that bookkeeping actually
runs on.

Built for a precious-metals and coin dealer workflow, but the business details
(name, categories, code scheme, accounting rules) are **loaded from a config
file**, so it adapts to any similar business without touching the code.

## What it does

- **Chat** — a QuickBooks assistant that answers in the context of your business.
  The system prompt is assembled from your config (categories, stock-code scheme,
  accounting rules), so the AI stays on-domain.
- **Spreadsheet tools** — upload an Excel/CSV and get it parsed, column-mapped,
  and validated for one of four jobs:
  - **Sales orders** — map rows to QuickBooks fields and flag missing/invalid ones
  - **Stock codes** — parse an item-code list and catch duplicates
  - **Inventory** — flag items at or below their reorder point
  - **Duplicates** — find repeated transactions by name + amount + date
- **Reconciliation** — compare a vendor export against QuickBooks data and let the
  AI explain each discrepancy and how to fix it.
- **Export** — write any result back out as a formatted `.xlsx`.

## What I actually built (vs. what the AI does)

The engineering here is the backend, not the model call. The genuinely hard parts:

- **Fuzzy column auto-mapping** (`parsers.py`): real exports never use the same
  headers, so each parser guesses which column means what from keyword lists.
- **Validation and duplicate logic**: per-row error collection, reorder-point
  math, and keyed duplicate detection.
- **The Excel pipeline**: reading mixed CSV encodings, cleaning NaNs, and
  generating styled workbooks.

The Claude call is a single function that takes the parsed data and the business
context and returns analysis. The model is one component, not the product.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env            # add your ANTHROPIC_API_KEY
cp config.example.json config.json   # edit for your business (gitignored)
python app.py                   # http://127.0.0.1:5001
```

Get an Anthropic API key at https://console.anthropic.com/.

## Configuration

`config.json` (gitignored; falls back to `config.example.json`) holds the
business context the assistant uses:

```json
{
  "business_name": "Acme Coin & Bullion",
  "industry": "Precious Metals / Coin Dealer",
  "inventory_categories": ["GOLD", "SILVER", "PLATINUM", "PALLADIUM", "NUMISMATIC", "FABRICATION"],
  "code_guide": "How your stock codes are structured...",
  "accounting_rules": ["FIFO costing", "Form 8300 over $10,000", "..."]
}
```

No business details are hardcoded, so your real config never has to be committed.

## Security notes

- Set `FLASK_DEBUG=0` (the default). Never run with the debugger on a reachable host.
- Set `ULTRON_APP_TOKEN` to require an `X-App-Token` header on POST requests. Without
  it, anyone who can reach the server can send chat requests and spend your API
  credits. In the UI, enter the same value under Settings > App Token; it is kept
  in the browser's sessionStorage and sent on every POST. Uploads are capped at 10 MB.
- The app binds to `127.0.0.1` by default. Only change `HOST` behind your own auth.

## Testing

```bash
pytest
```

The parsing and validation logic (the real engineering) is covered by unit tests
in `tests/`.

## Limitations

- It does **not** connect to the QuickBooks API yet — it prepares and validates
  data for import and explains what to do, but the push is still manual. Live QB
  integration is the obvious next step.
- The AI's accounting guidance is a helper, not a substitute for an accountant;
  verify anything tax-related.
- Analysis quality depends on the config describing your business accurately.

## Layout

```
app.py              Flask app: routes, config loading, lazy Claude client
parsers.py          Pure parsing/validation functions (unit-tested)
templates/index.html  Single-page UI
config.example.json Example business config (copy to config.json)
tests/              Parser unit tests
```
