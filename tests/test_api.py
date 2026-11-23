"""API tests using Flask's test client with a throwaway SQLite database."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.client = create_app(db_path=self.db_path).test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    # -- helpers ------------------------------------------------------------

    def add_member(self, name):
        resp = self.client.post("/api/v1/members", json={"name": name})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        return resp.get_json()["id"]

    def seed_two_members(self):
        return self.add_member("Sahil"), self.add_member("Tushar")

    def add_expense(self, **kwargs):
        return self.client.post("/api/v1/expenses", json=kwargs)

    # -- members --------------------------------------------------------------

    def test_health(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    def test_create_and_list_members(self):
        a, b = self.seed_two_members()
        resp = self.client.get("/api/v1/members")
        names = [m["name"] for m in resp.get_json()["members"]]
        self.assertEqual(names, ["Sahil", "Tushar"])
        self.assertNotEqual(a, b)

    def test_member_name_required(self):
        resp = self.client.post("/api/v1/members", json={"name": "  "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "invalid_input")

    def test_duplicate_member_rejected(self):
        self.add_member("Sahil")
        resp = self.client.post("/api/v1/members", json={"name": "Sahil"})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.get_json()["error"]["code"], "duplicate_member")

    # -- expenses -------------------------------------------------------------

    def test_expense_defaults_to_equal_split_over_all_members(self):
        a, b = self.seed_two_members()
        resp = self.add_expense(description="Chai", amount_paise=5000, paid_by=a, category="chai")
        self.assertEqual(resp.status_code, 201, resp.get_json())
        body = resp.get_json()
        shares = {s["member_id"]: s["amount_paise"] for s in body["shares"]}
        self.assertEqual(shares, {a: 2500, b: 2500})

    def test_equal_split_remainder_is_deterministic_and_exact(self):
        a, b = self.seed_two_members()
        resp = self.add_expense(
            description="Odd amount", amount_paise=101, paid_by=a,
            split={"type": "equal", "member_ids": [a, b]},
        )
        self.assertEqual(resp.status_code, 201, resp.get_json())
        shares = {s["member_id"]: s["amount_paise"] for s in resp.get_json()["shares"]}
        self.assertEqual(sum(shares.values()), 101)
        self.assertEqual(shares, {a: 51, b: 50})

    def test_exact_split_must_sum_to_amount(self):
        a, b = self.seed_two_members()
        resp = self.add_expense(
            description="Bad exact", amount_paise=1000, paid_by=a,
            split={"type": "exact", "shares": [{"member_id": a, "amount_paise": 400},
                                               {"member_id": b, "amount_paise": 400}]},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "invalid_split")

    def test_exact_split_accepted(self):
        a, b = self.seed_two_members()
        resp = self.add_expense(
            description="Treat", amount_paise=1000, paid_by=a,
            split={"type": "exact", "shares": [{"member_id": a, "amount_paise": 200},
                                               {"member_id": b, "amount_paise": 800}]},
        )
        self.assertEqual(resp.status_code, 201, resp.get_json())

    def test_expense_validation(self):
        a, _ = self.seed_two_members()
        self.assertEqual(self.add_expense(amount_paise=100, paid_by=a).status_code, 400)  # no description
        self.assertEqual(self.add_expense(description="x", amount_paise=-5, paid_by=a).status_code, 400)
        self.assertEqual(self.add_expense(description="x", amount_paise=100, paid_by=999).status_code, 400)
        self.assertEqual(self.add_expense(description="x", amount_paise=100, paid_by=a, category="gold").status_code, 400)
        self.assertEqual(self.add_expense(description="x", amount_paise=100, paid_by=a, date="22/11/2026").status_code, 400)

    def test_expense_requires_members(self):
        resp = self.add_expense(description="x", amount_paise=100, paid_by=1)
        self.assertEqual(resp.status_code, 400)

    def test_get_and_delete_expense(self):
        a, b = self.seed_two_members()
        created = self.add_expense(description="Chai", amount_paise=2000, paid_by=a).get_json()
        resp = self.client.get(f"/api/v1/expenses/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.delete(f"/api/v1/expenses/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/expenses/{created['id']}").status_code, 404)

    # -- balances and settlements --------------------------------------------

    def test_balances_and_settlement(self):
        a, b = self.seed_two_members()
        # Sahil pays 100 (10000 paise) split equally: each owes 50.
        self.add_expense(description="Dinner", amount_paise=10000, paid_by=a)
        resp = self.client.get("/api/v1/balances")
        balances = {x["member_id"]: x["net_paise"] for x in resp.get_json()["balances"]}
        self.assertEqual(balances[a], 5000)   # is owed
        self.assertEqual(balances[b], -5000)  # owes
        self.assertEqual(sum(balances.values()), 0)

        resp = self.client.get("/api/v1/settlements")
        settlements = resp.get_json()["settlements"]
        self.assertEqual(len(settlements), 1)
        s = settlements[0]
        self.assertEqual((s["from_member_id"], s["to_member_id"], s["amount_paise"]), (b, a, 5000))

    def test_balances_even_out_after_repayment(self):
        a, b = self.seed_two_members()
        self.add_expense(description="Dinner", amount_paise=10000, paid_by=a)
        # Tushar pays back by covering an equal expense himself.
        self.add_expense(description="Movie", amount_paise=10000, paid_by=b)
        resp = self.client.get("/api/v1/balances")
        self.assertTrue(all(x["net_paise"] == 0 for x in resp.get_json()["balances"]))
        self.assertEqual(self.client.get("/api/v1/settlements").get_json()["settlements"], [])

    # -- demo helpers -----------------------------------------------------------

    def test_seed_and_reset(self):
        resp = self.client.post("/api/v1/seed")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["expense_count"], 4)
        balances = self.client.get("/api/v1/balances").get_json()["balances"]
        self.assertEqual(sum(b["net_paise"] for b in balances), 0)
        resp = self.client.post("/api/v1/reset")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/members").get_json()["members"], [])

    def test_cors_headers_present(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main(verbosity=2)
