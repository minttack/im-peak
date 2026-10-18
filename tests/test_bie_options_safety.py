import tempfile
import unittest
from pathlib import Path

from bie_options_safety import ReservationLedger, assess_proposal, live_order_allowed, load_policy


class OptionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stop = Path(self.tmp.name) / "stop.flag"
        self.account = {
            "authenticated": True, "dedicated_agentic_account": True,
            "options_eligible": True, "buying_power_verified": True,
            "holdings_verified": True, "open_orders_verified": True,
            "approval_status_verified": True, "available_buying_power_usd": "20.00",
            "existing_option_risk_usd": "0.00", "pending_option_commitments_usd": "0.00",
            "new_option_debits_today_usd": "0.00",
        }
        self.contract = {
            "symbol": "SPY", "option_type": "call", "action": "BUY_TO_OPEN",
            "quantity": 1, "multiplier": 100, "expiration": "2026-10-23",
            "strike_usd": "700.00", "bid_usd": "0.03", "ask_usd": "0.04",
            "limit_price_usd": "0.04", "estimated_fees_usd": "0.03",
            "quote_timestamp": "2026-10-18T15:00:00Z",
        }
        self.now = "2026-10-18T15:00:30Z"

    def tearDown(self):
        self.tmp.cleanup()

    def assess(self):
        return assess_proposal(account=self.account, contract=self.contract,
                               now=self.now, stop_file=self.stop)

    def test_exact_long_option_can_be_proposed_but_never_ordered(self):
        result = self.assess()
        self.assertTrue(result["proposal_ready"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual("4.03", result["maximum_debit_usd"])
        self.assertFalse(live_order_allowed())

    def test_emergency_stop_blocks_proposal(self):
        self.stop.write_text("STOP\n")
        result = self.assess()
        self.assertFalse(result["proposal_ready"])
        self.assertIn("EMERGENCY_STOP_LATCHED", result["reasons"])

    def test_stale_quote_and_zero_dte_fail(self):
        self.contract["quote_timestamp"] = "2026-10-18T14:00:00Z"
        self.contract["expiration"] = "2026-10-18"
        result = self.assess()
        self.assertIn("STALE_OR_FUTURE_QUOTE", result["reasons"])
        self.assertIn("ZERO_DTE_OR_EXPIRED", result["reasons"])

    def test_multiplier_fee_and_daily_limits_are_included(self):
        self.contract["multiplier"] = 1
        self.contract["estimated_fees_usd"] = "2.00"
        self.account["new_option_debits_today_usd"] = "4.00"
        result = self.assess()
        self.assertIn("MULTIPLIER_NOT_ALLOWED", result["reasons"])
        self.assertIn("OVER_DAILY_DEBIT_LIMIT", result["reasons"])

    def test_unverified_account_and_insufficient_cash_fail(self):
        self.account["open_orders_verified"] = False
        self.account["available_buying_power_usd"] = "1.00"
        result = self.assess()
        self.assertIn("ACCOUNT_OPEN_ORDERS_VERIFIED_MISSING", result["reasons"])
        self.assertIn("INSUFFICIENT_BUYING_POWER", result["reasons"])

    def test_duplicate_reservation_survives_restart(self):
        result = self.assess()
        path = Path(self.tmp.name) / "ledger.json"
        key = ReservationLedger(path).reserve(result)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ReservationLedger(path).reserve(result)
        ReservationLedger(path).reconcile(key, broker_status="partially_filled",
                                          broker_open_orders_verified=True)

    def test_reconciliation_fails_closed_without_broker_check(self):
        result = self.assess()
        ledger = ReservationLedger(Path(self.tmp.name) / "ledger.json")
        key = ledger.reserve(result)
        with self.assertRaisesRegex(ValueError, "not verified"):
            ledger.reconcile(key, broker_status="rejected", broker_open_orders_verified=False)

    def test_policy_cannot_enable_options(self):
        policy = load_policy()
        policy["options_enabled"] = True
        result = assess_proposal(account=self.account, contract=self.contract, now=self.now,
                                 policy=policy, stop_file=self.stop)
        self.assertIn("INVALID_OR_MISSING_VERIFIED_INPUT", result["reasons"])


if __name__ == "__main__":
    unittest.main()
