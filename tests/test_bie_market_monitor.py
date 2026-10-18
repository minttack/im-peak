import json
from pathlib import Path
import tempfile
import unittest

import bie_market_monitor as m
from bie_order_execution import OrderSubmissionDisabled, submit_order


class MarketMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.snapshot = self.root / "snapshot.json"
        self.journal = self.root / "journal.json"
        self.snapshot.write_text(json.dumps({
            "source": "Robinhood Trading MCP", "received_at_utc": "2026-10-18T15:00:30Z",
            "requested_symbols": ["META", "SPY"],
            "raw_quote_response": {"content": [{"text": json.dumps([
                {"symbol": "META", "last_trade_price": "610.25", "last_trade_time": "2026-10-18T15:00:20Z"},
                {"symbol": "SPY", "mark_price": "690.10"}])}]}
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_quote_snapshot_is_normalized_with_missing_timestamp_warning(self):
        result = m.ingest_quote_snapshot(self.snapshot, self.journal)
        self.assertEqual(2, result["quotes"])
        doc = json.loads(self.journal.read_text())
        spy = next(q for q in doc["quotes"][0]["quotes"] if q["symbol"] == "SPY")
        self.assertTrue(spy["warnings"])
        self.assertIn("not converted to completed OHLCV", doc["quotes"][0]["h140_use"])

    def test_snapshot_deduplication_persists(self):
        m.ingest_quote_snapshot(self.snapshot, self.journal)
        result = m.ingest_quote_snapshot(self.snapshot, self.journal)
        self.assertEqual("duplicate", result["status"])

    def test_trade_quote_and_venue_timestamp_beat_later_historical_close(self):
        payload = json.loads(self.snapshot.read_text())
        payload["raw_quote_response"] = {"content": [{"text": json.dumps([
            {"symbol": "META", "last_trade_price": "709.34",
             "venue_last_trade_time": "2026-10-18T15:00:20Z"},
            {"symbol": "META", "price": "736.72"},
            {"symbol": "SPY", "mark_price": "690.10",
             "updated_at": "2026-10-18T15:00:25Z"},
        ])}]}
        self.snapshot.write_text(json.dumps(payload))
        m.ingest_quote_snapshot(self.snapshot, self.journal)
        quotes = json.loads(self.journal.read_text())["quotes"][0]["quotes"]
        meta = next(q for q in quotes if q["symbol"] == "META")
        self.assertEqual(709.34, meta["price_usd"])
        self.assertEqual("last_trade_price", meta["price_field"])
        self.assertEqual("2026-10-18T15:00:20+00:00", meta["provider_timestamp_utc"])
        self.assertEqual([], meta["warnings"])

    def test_old_normalization_is_repaired_from_same_snapshot(self):
        m.ingest_quote_snapshot(self.snapshot, self.journal)
        doc = json.loads(self.journal.read_text())
        doc["quotes"][0].pop("normalizer_version")
        doc["quotes"][0]["quotes"] = [{"symbol": "META", "price_usd": 1}]
        self.journal.write_text(json.dumps(doc))
        result = m.ingest_quote_snapshot(self.snapshot, self.journal)
        self.assertEqual("reprocessed_with_new_normalizer", result["status"])
        repaired = json.loads(self.journal.read_text())["quotes"][0]
        self.assertEqual(m.NORMALIZER_VERSION, repaired["normalizer_version"])
        self.assertEqual(2, len(repaired["quotes"]))

    def _packet(self):
        return {"schema": "bie.h140.prospective-prediction.v1", "trade_action": "NO_TRADE_RESEARCH",
                "symbol": "META", "instrument_type": "stock", "probability_up": 0.6,
                "generated_at_utc": "2026-10-18T15:00:00Z", "source_cutoff_utc": "2026-10-17T21:00:00Z",
                "model_name": "all_evidence", "horizon": "1 completed session",
                "source_report_sha256": "a" * 64, "hypothesis": "frozen model transfers",
                "falsifier": "Brier gain is nonpositive", "next_experiment": "resolve on the next completed session"}

    def test_prediction_is_frozen_then_resolved_only_with_later_evidence(self):
        packet = self.root / "packet.json"; packet.write_text(json.dumps(self._packet()))
        prediction_id = m.freeze_prediction(packet, self.journal)
        with self.assertRaisesRegex(ValueError, "not subsequent"):
            m.resolve_prediction(prediction_id, outcome_up=True, observed_at_utc="2026-10-18T14:00:00Z",
                                 source_ref="reviewed daily bar", journal_path=self.journal)
        outcome = m.resolve_prediction(prediction_id, outcome_up=True, observed_at_utc="2026-10-19T21:00:00Z",
                                       source_ref="reviewed daily bar", journal_path=self.journal)
        self.assertEqual(0.16, outcome["brier_score"])

    def test_future_cutoff_and_trade_action_are_rejected(self):
        packet = self._packet(); packet["source_cutoff_utc"] = "2026-10-19T00:00:00Z"
        path = self.root / "packet.json"; path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "future-data"):
            m.freeze_prediction(path, self.journal)
        packet["source_cutoff_utc"] = "2026-10-17T00:00:00Z"; packet["trade_action"] = "BUY"
        path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "trade action"):
            m.freeze_prediction(path, self.journal)

    def test_order_submission_is_structurally_disabled(self):
        with self.assertRaises(OrderSubmissionDisabled):
            submit_order(symbol="META")


if __name__ == "__main__":
    unittest.main()
