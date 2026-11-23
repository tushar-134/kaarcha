# Kharcha Split

A runnable local demo that joins Tushar's frontend with Nigamananda's Flask + SQLite backend. Log fictional shared expenses, split them equally or by exact shares, and see who owes whom. No payments are made.

## Start

Requires Python 3.10 or newer. From this folder:

```bash
python -m venv .venv
```

Activate the environment:

- macOS/Linux: `source .venv/bin/activate`
- Windows: `.venv\Scripts\activate`

Then:

```bash
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000/?demo` in the same computer's browser to load fictional examples. For an empty ledger, use `http://127.0.0.1:5000/`. The empty app creates the two demo members, Tushar and Nigamananda. The example amounts and events are invented, not anyone's financial records.

One server serves both the UI and API. No separate frontend process or build step is needed. To choose a port: `python run.py --port 5050`, then open that port. To choose a database file: `python run.py --db demo.db`.

Stop with Ctrl+C. Expenses persist in the local `kharcha.db` SQLite file across reloads and restarts. No database is included in this download.

## What works

- Add and delete expenses, four categories: chai, food, trip, other.
- Equal splits with deterministic remainder paise, or exact custom shares.
- Server-computed balances and greedy suggested repayments.
- JSON API validation and clear form errors.
- Offline save failures retain the form and show an error. There is no automatic localStorage fallback or hidden change of data store.
- Responsive interface checked at desktop, 390px phone width, and 320px width.

## Important limits

This is a localhost-only, dummy-data demo. It is not a shared online app. It binds to `127.0.0.1`; it has no authentication and open CORS. Do not expose it through a tunnel, shared network, or external host, or enter real financial records. Hosting, access control and real-data sharing have not been set up.

The red **Demo reset: sab entries delete** button deletes all expenses and members after a warning, then recreates the member names. It does not record a repayment or retain history. Delete is also permanent. Settlement suggestions do not move money and are not guaranteed to use the fewest transfers.

The `?demo` startup option seeds only when there are no expenses; seeding replaces the current members. Reload without `?demo` after resetting if you want to keep an empty ledger.

## Tests

```bash
python -m unittest discover -s tests -v
```

18 test methods pass, including malformed input cases, calendar-date validation, paise rounding, zero-sum balances, JSON error responses, and serving the actual frontend.

A separate real-browser integration test starts and stops the actual backend against a temporary SQLite file:

```bash
python -m pip install playwright
python tests/joined_browser.py
```

That test currently expects Google Chrome at `/usr/bin/google-chrome` and ports 5000 free. It does not use the peer's mock API. Its 24 checks cover equal/custom splits, API errors, reload persistence, deletion, reset confirmation/cancellation, offline errors, phone-width layout, JavaScript errors and process restart. On startup failure, unknown balances/expenses stay hidden. If a later request fails, previously loaded figures are explicitly labelled stale and not currently verified. Screenshots and the latest check list are in `proof/`.

## Project layout

- `run.py`: loopback-only server entry point, debug disabled.
- `app/`: Flask API, SQLite schema, validation, split and balance math, fictional seed data.
- `integration/frontend/`: integrated HTML, CSS and vanilla JavaScript.
- `API_CONTRACT.md`: agreed v1.1 interface and integration notes.
- `tests/`: automated tests.
- `proof/`: desktop/mobile and error-state screenshots, joined-test results.

## Integration changes

The revised frontend was adapted to run from the backend's same origin. The API contract remains v1.1. Automatic localStorage fallback was removed to avoid a save appearing successful in a different store after a network failure. Save/delete/reset errors are visible, submit buttons guard duplicate requests, and reset remains explicitly destructive. Small category letter badges replace unsupported emoji glyphs for consistent rendering.
