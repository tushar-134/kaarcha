"""Dummy demo data. Names are the two collaborators; amounts are fictional."""
from .logic import equal_shares

DEMO_MEMBERS = ["Tushar", "Nigamananda"]

DEMO_EXPENSES = [
    # (description, amount_paise, paid_by_index, category, date)
    ("Chai at tapri", 4000, 0, "chai", "2026-11-20"),
    ("Momos and cold drinks", 18000, 1, "food", "2026-11-21"),
    ("Auto to Esplanade", 15000, 0, "trip", "2026-11-21"),
    ("Dinner at dhaba", 32000, 1, "food", "2026-11-22"),
]


def seed_demo(db):
    member_ids = []
    for name in DEMO_MEMBERS:
        cur = db.execute(
            "INSERT INTO members (name, created_at) VALUES (?, ?)",
            (name, "2026-11-20T00:00:00+00:00"),
        )
        member_ids.append(cur.lastrowid)

    for description, amount, payer_idx, category, date in DEMO_EXPENSES:
        cur = db.execute(
            "INSERT INTO expenses (description, amount_paise, paid_by, category, date, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (description, amount, member_ids[payer_idx], category, date, "2026-11-22T00:00:00+00:00"),
        )
        for share in equal_shares(amount, member_ids):
            db.execute(
                "INSERT INTO expense_shares (expense_id, member_id, amount_paise) VALUES (?, ?, ?)",
                (cur.lastrowid, share["member_id"], share["amount_paise"]),
            )
