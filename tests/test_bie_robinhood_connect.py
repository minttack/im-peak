"""Offline regression tests for BIE's fail-closed Robinhood adapter."""
import tempfile
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bie_robinhood_connect as c

class ReadOnlyTest(unittest.TestCase):
    def test_fixed_readonly_call_known_signature(self):
        self.assertEqual(
            c.fixed_readonly_quote_arguments(("SPY", "QQQ")),
            {"symbols": ["SPY", "QQQ"]},
        )

    def test_fixed_readonly_call_validates_tickers(self):
        with self.assertRaises(ValueError):
            c.fixed_readonly_quote_arguments(("SPY", "../BAD"))

    def test_only_quote_tool_is_allowlisted(self):
        self.assertEqual(c.READ_ONLY_ALLOWLIST, frozenset(("get_equity_quotes",)))
        self.assertNotIn("place_option_order", c.READ_ONLY_ALLOWLIST)
        self.assertNotIn("place_equity_order", c.READ_ONLY_ALLOWLIST)

    def test_can_construct_allowed_quote_args(self):
        d = {"properties": {"symbols": {"type": "array", "items": {"type": "string"}}},
             "required": ["symbols"]}
        self.assertEqual(c.quote_arguments(d, ("SPY", "QQQ")), {"symbols": ["SPY", "QQQ"]})

    def test_nullable_array_schema(self):
        d = {"properties": {"symbols": {
            "anyOf": [
                {"type": "array", "items": {"type": "string"}},
                {"type": "null"}
            ]}}, "required": ["symbols"]}
        self.assertEqual(c.quote_arguments(d, ("SPY", "QQQ")),
                         {"symbols": ["SPY", "QQQ"]})

    def test_type_array_nullable_union(self):
        d = {"properties": {"symbols": {
            "type": ["array", "null"], "items": {"type": "string"}}},
             "required": ["symbols"]}
        self.assertEqual(c.quote_arguments(d, ("SPY",)), {"symbols": ["SPY"]})

    def test_quote_diagnostics_no_secrets(self):
        d = {"properties": {"symbols": {
            "anyOf": [{"type": "array", "items": {"type": "string"}},
                      {"type": "null"}],
            "description": "OAuth bearer: private value is never displayed"}},
            "required": ["symbols"]}
        diagnostic = c.safe_quote_schema_diagnostic(d)
        self.assertIn("symbols", diagnostic["fields"])
        self.assertNotIn("private value", str(diagnostic))

    def test_nullable_unconstrained_list_items(self):
        d = {"properties": {"symbols": {"anyOf": [
            {"type": "array", "items": {}}, {"type": "null"}]}},
            "required": ["symbols"]}
        self.assertEqual(c.quote_arguments(d, ("SPY", "QQQ")),
                         {"symbols": ["SPY", "QQQ"]})

    def test_array_with_implicit_items(self):
        d = {"properties": {"symbols": {"type": "array"}},
             "required": ["symbols"]}
        self.assertEqual(c.quote_arguments(d, ("SPY",)),
                         {"symbols": ["SPY"]})

    def test_rejects_incompatible_array_items(self):
        d = {"properties": {"symbols": {"type": "array",
                                        "items": {"type": "number"}}},
             "required": ["symbols"]}
        self.assertIsNone(c.quote_arguments(d, ("SPY",)))

    def test_schema_requirements_fail_closed(self):
        d = {"properties": {"symbols": {"type": "array", "items": {"type": "string"}},
                            "account_id": {"type": "string"}},
             "required": ["account_id", "symbols"]}
        self.assertIsNone(c.quote_arguments(d, ("SPY",)))

    def test_bogus_schema_fails(self):
        self.assertIsNone(c.quote_arguments({}, ("SPY",)))
        self.assertIsNone(c.quote_arguments({"properties": {"symbols": {"type": "number"}}}, ("SPY",)))

    def test_ticker_validation(self):
        self.assertEqual(c.symbols_from_text("spy, qqq"), ("SPY", "QQQ"))
        with self.assertRaises(ValueError):
            c.symbols_from_text("SPY,../CODE")
        with self.assertRaises(ValueError):
            c.symbols_from_text("")

    def test_status_does_not_claim_orders(self):
        with tempfile.TemporaryDirectory() as d:
            old_runtime, old_status = c.RUNTIME, c.STATUS
            try:
                c.RUNTIME = Path(d)
                c.STATUS = Path(d) / "status.json"
                c.status("CONNECTION_TEST_PASSED")
                raw = c.STATUS.read_text()
                self.assertIn('"live_orders_enabled": false', raw)
            finally:
                c.RUNTIME, c.STATUS = old_runtime, old_status

if __name__ == "__main__":
    unittest.main()
