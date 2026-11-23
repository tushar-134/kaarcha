# Kharcha Split - API Contract v1.1 (agreed interface)

Base URL (local dev): `http://localhost:5000/api/v1`

## Conventions

- All requests and responses are JSON.
- **Money is always integer paise** (`amount_paise`, `100 = ₹1.00`). No floats anywhere. The frontend divides by 100 for display.
- Dates are `YYYY-MM-DD` strings. `created_at` is an ISO-8601 UTC timestamp.
- Errors always look like: `{"error": {"code": "...", "message": "..."}}` with a matching HTTP status (400 invalid input, 404 not found, 409 `duplicate_member`).
- CORS is open (`Access-Control-Allow-Origin: *`) so any local dev frontend can call it.
- No auth. The server binds to 127.0.0.1 (localhost) only, so it is unreachable from other machines. This is a local dummy-data demo, not for real deployment or a shared network.

## Response shape rule

- List/report endpoints return a named wrapper object: `{"members": [...]}`, `{"expenses": [...]}`, `{"balances": [...]}`, `{"settlements": [...]}`.
- Single-resource endpoints return the bare object with no wrapper: `GET /expenses/{id}`, `POST /expenses`, `POST /members`, `POST /seed` summary, `POST /reset` summary, `GET /health`.
- Error responses always use the `{"error": ...}` shape above, never a bare object.

## Exact object shapes

**Member**
```json
{"id": 1, "name": "Sahil", "created_at": "2026-11-22T00:00:00+00:00"}
```

**Expense**
```json
{
  "id": 5,
  "description": "Cutting chai",
  "amount_paise": 2000,
  "paid_by": 1,
  "category": "chai",
  "date": "2026-11-22",
  "created_at": "2026-11-22T18:10:03+00:00",
  "shares": [
    {"member_id": 1, "amount_paise": 1000},
    {"member_id": 2, "amount_paise": 1000}
  ]
}
```
`shares` always sums exactly to `amount_paise`.

**Balance**
```json
{"member_id": 1, "name": "Sahil", "paid_paise": 21000, "share_paise": 35500, "net_paise": -14500}
```
`net_paise = paid_paise - share_paise`. Positive: the group owes this member. Negative: they owe. Nets across members always sum to 0.

**Settlement**
```json
{"from_member_id": 1, "from_name": "Sahil", "to_member_id": 2, "to_name": "Tushar", "amount_paise": 14500}
```

## Endpoints

### `GET /health`
→ 200, `{"status": "ok"}`

### `GET /members`
→ 200, `{"members": [Member, ...]}` ordered by id.

### `POST /members`
Body: `{"name": "Sahil"}`
→ 201, bare Member object. 400 if name missing/blank, 409 if the name already exists.

Exact duplicate-name response (HTTP 409):
```json
{"error": {"code": "duplicate_member", "message": "a member with this name already exists"}}
```

### `GET /expenses`
→ 200, `{"expenses": [Expense, ...]}` newest first (by date, then id).

### `GET /expenses/{id}`
→ 200, bare Expense object. 404 if unknown id.

### `POST /expenses`
Body:
```json
{
  "description": "Cutting chai",
  "amount_paise": 2000,
  "paid_by": 1,
  "category": "chai",
  "date": "2026-11-22",
  "split": {"type": "equal", "member_ids": [1, 2]}
}
```
→ 201, bare Expense object including the computed `shares`.

- `description`: required, non-empty text, at most 200 characters.
- `amount_paise`: required, positive integer, at most 100000000000 paise.
- `paid_by`: required, an existing member id.
- `category`: optional, one of `chai`, `food`, `trip`, `other` (default `other`).
- `date`: optional, `YYYY-MM-DD`, defaults to today in Asia/Kolkata.
- `split`: optional. Three forms:
  - omitted → equal split across **all** members;
  - `{"type": "equal", "member_ids": [...]}` → equal across those members; leftover paise go one each to the first members in the list, so shares always sum exactly to `amount_paise`;
  - `{"type": "exact", "shares": [{"member_id": 1, "amount_paise": 500}, ...]}` → custom amounts, must sum exactly to `amount_paise` or the request is rejected with 400 `invalid_split`.

### `DELETE /expenses/{id}`
→ 200, `{"deleted": true, "id": 5}`. 404 if unknown id.

### `GET /balances`
→ 200, `{"balances": [Balance, ...]}` one entry per member.

### `GET /settlements`
→ 200, `{"settlements": [Settlement, ...]}`

Suggested transfers that settle everyone, built greedily: repeatedly match the largest debtor with the largest creditor. The suggestions are always valid (following them settles all balances), but the greedy heuristic does not guarantee the minimum possible number of transfers. Settlements are suggestions only; no money ever moves in the app.

### `POST /seed` (demo only)
Wipes the DB and loads dummy data: members Tushar and Nigamananda plus 4 sample expenses.
→ 200, `{"seeded": true, "members": [{"id": 1, "name": "Tushar"}, {"id": 2, "name": "Nigamananda"}], "expense_count": 4}`. Seed member summaries contain `id` and `name` only. IDs increase across resets; read returned IDs rather than hard-coding them.

### `POST /reset` (demo only)
Wipes all data. → 200, `{"reset": true}`

## Balance rules (the "hisaab" logic)

1. Every expense records who paid and each member's share in paise.
2. A member's net = everything they paid minus everything they consumed (their shares).
3. Settlements are greedy suggestions that reduce everyone to zero.

## Agreed demo decisions

- Fixed four categories, delete and re-add instead of editing, no list filters.
- Add-only API member management with unique names. Integrated UI starts with Tushar and Nigamananda; it does not expose a member-management form.
- Greedy settlement suggestions only, no per-pair historical debt report and no repayment recording.
- Reset is explicitly destructive demo deletion, not settlement.

## Joined app

`python run.py` serves both frontend and API on `http://127.0.0.1:5000`. Frontend calls same-origin `/api/v1`. It requires the backend; no automatic localStorage fallback. Add `?demo` to load fictional seed examples when the expense list is empty.
