import tempfile
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bie_safety import assess_paper_buy, live_order_allowed, load_policy, dollars

class SafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stop = Path(self.tmp.name) / "stop"
        self.k = dict(symbol="SPY", asset="etf", notional_usd="1.00",
                      available_cash_usd="20.00", filled_buys_today_usd="0.00",
                      pending_buys_today_usd="0.00", existing_invested_usd="0.00",
                      quote_age_seconds=20, stop_file=self.stop)
    def tearDown(self):
        self.tmp.cleanup()
    def check(self, reason, **changes):
        k = {**self.k, **changes}
        result = assess_paper_buy(**k)
        self.assertFalse(result["paper_candidate_allowed"], result)
        self.assertIn(reason, result["reasons"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual(result["submitted_orders"], 0)
    def test_policy(self):
        p = load_policy()
        self.assertEqual(p["starting_budget_usd"], "20.00")
        self.assertEqual(p["daily_new_buy_limit_usd"], "5.00")
        self.assertFalse(p["live_orders_enabled"])
    def test_valid_paper_only(self):
        r = assess_paper_buy(**self.k)
        self.assertTrue(r["paper_candidate_allowed"], r)
        self.assertFalse(r["live_order_allowed"])
    def test_emergency_stop(self):
        self.stop.touch()
        self.check("EMERGENCY_STOP")
    def test_order_limit(self):
        self.check("OVER_SINGLE_BUY_LIMIT", notional_usd="5.01")
    def test_cumulative_daily_filled(self):
        self.check("OVER_DAILY_BUY_LIMIT", filled_buys_today_usd="4.50")
    def test_cumulative_daily_pending(self):
        self.check("OVER_DAILY_BUY_LIMIT", pending_buys_today_usd="4.10")
    def test_cannot_overdraw(self):
        self.check("INSUFFICIENT_CASH", available_cash_usd="0.10")
    def test_total_budget(self):
        self.check("OVER_TOTAL_INVESTED_LIMIT", existing_invested_usd="19.50")
    def test_stale_quote(self):
        self.check("STALE_OR_INVALID_QUOTE", quote_age_seconds=300)
    def test_options_blocked(self):
        self.check("ASSET_NOT_ALLOWED", asset="option")
    def test_bad_input(self):
        self.check("INVALID_OR_MISSING_POLICY_OR_INPUT", notional_usd="-1.00")
        self.check("INVALID_OR_MISSING_POLICY_OR_INPUT", notional_usd="NaN")
        self.check("INVALID_OR_MISSING_POLICY_OR_INPUT", notional_usd="1.001")
    def test_bad_symbol(self):
        self.check("INVALID_SYMBOL", symbol="")
    def test_live_never_allowed(self):
        self.assertFalse(live_order_allowed())
        self.assertFalse(live_order_allowed("BUY", "SPY", "2.00"))
    def test_bad_policy_rejected(self):
        p = load_policy()
        self.check("INVALID_OR_MISSING_POLICY_OR_INPUT", policy={**p, "live_orders_enabled": True})
    def test_never_submits_live(self):
        r = assess_paper_buy(**self.k)
        self.assertEqual(r["submitted_orders"], 0)

if __name__ == "__main__":
    unittest.main()
