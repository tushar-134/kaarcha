"""HTTP API routes. All amounts are integer paise (INR)."""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request

from .db import get_db
from .logic import compute_balances, compute_settlements, equal_shares

api = Blueprint("api", __name__, url_prefix="/api/v1")

CATEGORIES = ("chai", "food", "trip", "other")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@api.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify({"error": {"code": err.code, "message": err.message}}), err.status


@api.errorhandler(404)
def handle_404(err):
    return jsonify({"error": {"code": "not_found", "message": "Resource not found"}}), 404


def json_object():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_input", "request body must be a JSON object")
    return body


def text_field(body, key, limit):
    value = body.get(key, "")
    if not isinstance(value, str) or len(value) > limit:
        raise ApiError(400, "invalid_input", f"{key} must be text of at most {limit} characters")
    return value.strip()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def member_exists(db, member_id):
    return db.execute("SELECT 1 FROM members WHERE id = ?", (member_id,)).fetchone() is not None


def expense_to_json(db, row):
    shares = db.execute(
        "SELECT member_id, amount_paise FROM expense_shares WHERE expense_id = ? ORDER BY member_id",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "description": row["description"],
        "amount_paise": row["amount_paise"],
        "paid_by": row["paid_by"],
        "category": row["category"],
        "date": row["date"],
        "created_at": row["created_at"],
        "shares": [dict(s) for s in shares],
    }


# ---- health ---------------------------------------------------------------

@api.get("/health")
def health():
    return jsonify({"status": "ok"})


# ---- members --------------------------------------------------------------

@api.get("/members")
def list_members():
    rows = get_db().execute("SELECT id, name, created_at FROM members ORDER BY id").fetchall()
    return jsonify({"members": [dict(r) for r in rows]})


@api.post("/members")
def create_member():
    body = json_object()
    name = text_field(body, "name", 80)
    if not name:
        raise ApiError(400, "invalid_input", "name is required")
    db = get_db()
    if db.execute("SELECT 1 FROM members WHERE name = ?", (name,)).fetchone():
        raise ApiError(409, "duplicate_member", "a member with this name already exists")
    cur = db.execute(
        "INSERT INTO members (name, created_at) VALUES (?, ?)", (name, now_iso())
    )
    db.commit()
    row = db.execute("SELECT id, name, created_at FROM members WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


# ---- expenses -------------------------------------------------------------

@api.get("/expenses")
def list_expenses():
    db = get_db()
    rows = db.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC").fetchall()
    return jsonify({"expenses": [expense_to_json(db, r) for r in rows]})


@api.post("/expenses")
def create_expense():
    body = json_object()
    db = get_db()

    description = text_field(body, "description", 200)
    if not description:
        raise ApiError(400, "invalid_input", "description is required")

    amount = body.get("amount_paise")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or amount > 100000000000:
        raise ApiError(400, "invalid_input", "amount_paise must be a positive integer (paise)")

    paid_by = body.get("paid_by")
    if type(paid_by) is not int or not member_exists(db, paid_by):
        raise ApiError(400, "invalid_input", "paid_by must be an existing member id")

    category = body.get("category", "other")
    if category not in CATEGORIES:
        raise ApiError(400, "invalid_input", f"category must be one of: {', '.join(CATEGORIES)}")

    date = body.get("date", datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"))
    try:
        if not isinstance(date, str) or not DATE_RE.fullmatch(date):
            raise ValueError()
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ApiError(400, "invalid_input", "date must be a valid YYYY-MM-DD date")

    split = body.get("split")
    all_member_ids = [r["id"] for r in db.execute("SELECT id FROM members ORDER BY id").fetchall()]
    if not all_member_ids:
        raise ApiError(400, "no_members", "create at least one member before adding expenses")

    if split is not None and not isinstance(split, dict):
        raise ApiError(400, "invalid_input", "split must be an object")
    if split is None:
        shares = equal_shares(amount, all_member_ids)
    elif split.get("type") == "equal":
        member_ids = split.get("member_ids", all_member_ids)
        if not isinstance(member_ids, list) or not member_ids:
            raise ApiError(400, "invalid_input", "split.member_ids must be a non-empty list")
        if any(type(mid) is not int for mid in member_ids):
            raise ApiError(400, "invalid_input", "member ids must be integers")
        if len(set(member_ids)) != len(member_ids):
            raise ApiError(400, "invalid_input", "split.member_ids contains duplicates")
        for mid in member_ids:
            if type(mid) is not int or not member_exists(db, mid):
                raise ApiError(400, "invalid_input", f"split member id {mid!r} does not exist")
        shares = equal_shares(amount, member_ids)
    elif split.get("type") == "exact":
        raw = split.get("shares")
        if not isinstance(raw, list) or not raw:
            raise ApiError(400, "invalid_input", "split.shares must be a non-empty list")
        shares = []
        seen = set()
        for s in raw:
            if not isinstance(s, dict):
                raise ApiError(400, "invalid_input", "each share must be an object")
            mid, amt = s.get("member_id"), s.get("amount_paise")
            if type(mid) is not int or not member_exists(db, mid):
                raise ApiError(400, "invalid_input", f"split member id {mid!r} does not exist")
            if mid in seen:
                raise ApiError(400, "invalid_input", "split.shares contains a duplicate member")
            if not isinstance(amt, int) or isinstance(amt, bool) or amt < 0:
                raise ApiError(400, "invalid_input", "share amount_paise must be a non-negative integer")
            seen.add(mid)
            shares.append({"member_id": mid, "amount_paise": amt})
        if sum(s["amount_paise"] for s in shares) != amount:
            raise ApiError(400, "invalid_split", "exact shares must add up to amount_paise")
    else:
        raise ApiError(400, "invalid_input", "split.type must be 'equal' or 'exact'")

    cur = db.execute(
        "INSERT INTO expenses (description, amount_paise, paid_by, category, date, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (description, amount, paid_by, category, date, now_iso()),
    )
    expense_id = cur.lastrowid
    for s in shares:
        db.execute(
            "INSERT INTO expense_shares (expense_id, member_id, amount_paise) VALUES (?, ?, ?)",
            (expense_id, s["member_id"], s["amount_paise"]),
        )
    db.commit()
    row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return jsonify(expense_to_json(db, row)), 201


@api.get("/expenses/<int:expense_id>")
def get_expense(expense_id):
    db = get_db()
    row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "expense not found")
    return jsonify(expense_to_json(db, row))


@api.delete("/expenses/<int:expense_id>")
def delete_expense(expense_id):
    db = get_db()
    if db.execute("SELECT 1 FROM expenses WHERE id = ?", (expense_id,)).fetchone() is None:
        raise ApiError(404, "not_found", "expense not found")
    db.execute("DELETE FROM expense_shares WHERE expense_id = ?", (expense_id,))
    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    return jsonify({"deleted": True, "id": expense_id})


# ---- balances and settlements --------------------------------------------

@api.get("/balances")
def get_balances():
    return jsonify({"balances": compute_balances(get_db())})


@api.get("/settlements")
def get_settlements():
    balances = compute_balances(get_db())
    return jsonify({"settlements": compute_settlements(balances)})


# ---- demo helpers (local demo only) ---------------------------------------

@api.post("/reset")
def reset_data():
    db = get_db()
    db.execute("DELETE FROM expense_shares")
    db.execute("DELETE FROM expenses")
    db.execute("DELETE FROM members")
    db.commit()
    return jsonify({"reset": True})


@api.post("/seed")
def seed_data():
    from .seed import seed_demo

    db = get_db()
    db.execute("DELETE FROM expense_shares")
    db.execute("DELETE FROM expenses")
    db.execute("DELETE FROM members")
    seed_demo(db)
    db.commit()
    members = db.execute("SELECT id, name FROM members ORDER BY id").fetchall()
    expenses = db.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()
    return jsonify({"seeded": True, "members": [dict(m) for m in members], "expense_count": expenses["n"]})
