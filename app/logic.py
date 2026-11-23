"""Balance and settlement math. All amounts are integer paise (INR)."""


def equal_shares(amount_paise, member_ids):
    """Split an amount as equally as possible.

    The remainder paise go one each to the first members in the given order,
    so the result is deterministic and always sums to amount_paise.
    """
    n = len(member_ids)
    base, rem = divmod(amount_paise, n)
    return [
        {"member_id": mid, "amount_paise": base + (1 if i < rem else 0)}
        for i, mid in enumerate(member_ids)
    ]


def compute_balances(db):
    """Net balance per member, in paise.

    net = total paid - total share owed.
    Positive net: the group owes this member. Negative: they owe the group.
    Nets always sum to zero.
    """
    members = db.execute("SELECT id, name FROM members ORDER BY id").fetchall()
    paid = {
        row["paid_by"]: row["total"]
        for row in db.execute(
            "SELECT paid_by, SUM(amount_paise) AS total FROM expenses GROUP BY paid_by"
        ).fetchall()
    }
    owed = {
        row["member_id"]: row["total"]
        for row in db.execute(
            "SELECT member_id, SUM(amount_paise) AS total FROM expense_shares GROUP BY member_id"
        ).fetchall()
    }
    balances = []
    for m in members:
        p = paid.get(m["id"], 0) or 0
        o = owed.get(m["id"], 0) or 0
        balances.append(
            {
                "member_id": m["id"],
                "name": m["name"],
                "paid_paise": p,
                "share_paise": o,
                "net_paise": p - o,
            }
        )
    return balances


def compute_settlements(balances):
    """Greedy debt simplification.

    Returns a valid set of transfers that settles everyone, built by
    repeatedly matching the largest debtor with the largest creditor.
    This is a simple heuristic; it does not guarantee the minimum possible
    number of transfers, but every suggestion leaves all balances settled.
    """
    debtors = sorted(
        (b for b in balances if b["net_paise"] < 0), key=lambda b: b["net_paise"]
    )
    creditors = sorted(
        (b for b in balances if b["net_paise"] > 0),
        key=lambda b: b["net_paise"],
        reverse=True,
    )
    settlements = []
    i = j = 0
    remaining_debt = [-d["net_paise"] for d in debtors]
    remaining_credit = [c["net_paise"] for c in creditors]
    while i < len(debtors) and j < len(creditors):
        amount = min(remaining_debt[i], remaining_credit[j])
        if amount > 0:
            settlements.append(
                {
                    "from_member_id": debtors[i]["member_id"],
                    "from_name": debtors[i]["name"],
                    "to_member_id": creditors[j]["member_id"],
                    "to_name": creditors[j]["name"],
                    "amount_paise": amount,
                }
            )
        remaining_debt[i] -= amount
        remaining_credit[j] -= amount
        if remaining_debt[i] == 0:
            i += 1
        if remaining_credit[j] == 0:
            j += 1
    return settlements
