#!/usr/bin/env python3
"""Prospective BIE market evidence and prediction-outcome journal.

Robinhood quote snapshots are observations, never synthetic OHLCV bars. H140
continues to require reviewed completed daily history. This module performs no
networking and imports no brokerage order API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

SYMBOLS = frozenset(("META", "MSFT", "XOM", "AMZN", "JNJ", "SPY", "QQQ"))
SYMBOL_KEYS = ("symbol", "ticker", "instrument_symbol")
PRICE_KEYS = ("mark_price", "last_trade_price", "last_price", "price")
TIME_KEYS = ("venue_last_trade_time", "last_trade_time", "updated_at", "timestamp", "as_of")
SCHEMA = 1
NORMALIZER_VERSION = 2


def _time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def _price(value):
    if isinstance(value, bool):
        raise ValueError("invalid price")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("invalid price")
    return result


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)
    elif isinstance(value, str) and value[:1] in ("{", "["):
        try:
            yield from _walk(json.loads(value))
        except json.JSONDecodeError:
            return


def normalize_quotes(snapshot):
    """Extract only explicit symbol/price fields; preserve uncertainty."""
    if snapshot.get("source") != "Robinhood Trading MCP":
        raise ValueError("unexpected source")
    received = _time(snapshot["received_at_utc"])
    requested = snapshot.get("requested_symbols")
    if not isinstance(requested, list) or not requested or not set(requested) <= SYMBOLS:
        raise ValueError("unexpected requested symbols")
    found = {}
    quality = {}
    for item in _walk(snapshot.get("raw_quote_response")):
        symbol = next((item.get(k) for k in SYMBOL_KEYS if item.get(k)), None)
        if not isinstance(symbol, str) or symbol.upper() not in requested:
            continue
        price_key = next((k for k in PRICE_KEYS if item.get(k) is not None), None)
        if price_key is None:
            continue
        symbol = symbol.upper()
        provider_time = next((item.get(k) for k in TIME_KEYS if item.get(k)), None)
        warnings = []
        provider_utc = None
        if provider_time is None:
            warnings.append("provider_timestamp_missing; receipt time is not market time")
        else:
            try:
                provider_utc = _time(provider_time).isoformat()
                age = (received - _time(provider_time)).total_seconds()
                if age < -5 or age > 120:
                    warnings.append("provider_timestamp_future_or_stale")
            except (TypeError, ValueError):
                warnings.append("provider_timestamp_invalid")
        # Responses can contain separate current-quote and historical-close
        # records for one symbol. Keep the most specific current quote field;
        # traversal order must never let generic ``price`` overwrite a trade.
        rank = {"price": 1, "last_price": 2, "mark_price": 3,
                "last_trade_price": 4}[price_key]
        if rank > quality.get(symbol, 0):
            quality[symbol] = rank
            found[symbol] = {"symbol": symbol, "price_usd": _price(item[price_key]),
                             "price_field": price_key, "provider_timestamp_utc": provider_utc,
                             "received_at_utc": received.isoformat(), "warnings": warnings}
    missing = sorted(set(requested) - set(found))
    return [found[s] for s in sorted(found)], missing


def _read_store(path):
    path = Path(path)
    if not path.exists():
        return {"schema": SCHEMA, "quotes": [], "predictions": [], "outcomes": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError("unsupported evidence journal")
    return doc


def _write_store(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def ingest_quote_snapshot(snapshot_path, journal_path):
    raw = Path(snapshot_path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    snapshot = json.loads(raw)
    quotes, missing = normalize_quotes(snapshot)
    doc = _read_store(journal_path)
    previous = next((row for row in doc["quotes"] if row["snapshot_sha256"] == digest), None)
    if previous is not None and previous.get("normalizer_version") == NORMALIZER_VERSION:
        return {"status": "duplicate", "snapshot_sha256": digest}
    entry = {"snapshot_sha256": digest, "normalizer_version": NORMALIZER_VERSION,
                          "source": "Robinhood Trading MCP/get_equity_quotes",
                          "received_at_utc": _time(snapshot["received_at_utc"]).isoformat(),
                          "quotes": quotes, "missing_symbols": missing,
                          "reliability": "provider timestamp required for freshness; raw snapshot retained separately",
                          "h140_use": "prospective observation only; not converted to completed OHLCV"}
    if previous is None:
        doc["quotes"].append(entry)
        result_status = "recorded"
    else:
        # Deterministic repair from the same immutable raw snapshot.
        doc["quotes"][doc["quotes"].index(previous)] = entry
        result_status = "reprocessed_with_new_normalizer"
    _write_store(journal_path, doc)
    return {"status": result_status, "snapshot_sha256": digest,
            "quotes": len(quotes), "missing_symbols": missing}


def freeze_prediction(packet_path, journal_path):
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    if packet.get("schema") != "bie.h140.prospective-prediction.v1":
        raise ValueError("invalid prediction schema")
    if packet.get("trade_action") != "NO_TRADE_RESEARCH":
        raise ValueError("prediction packet attempted a trade action")
    if packet.get("symbol") not in SYMBOLS or packet.get("instrument_type") not in ("stock", "option"):
        raise ValueError("invalid instrument")
    probability = float(packet["probability_up"])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("invalid probability")
    generated = _time(packet["generated_at_utc"])
    cutoff = _time(packet["source_cutoff_utc"])
    if cutoff > generated:
        raise ValueError("future-data leakage")
    required = ("model_name", "horizon", "source_report_sha256", "hypothesis", "falsifier", "next_experiment")
    if any(not isinstance(packet.get(k), str) or not packet[k].strip() for k in required):
        raise ValueError("incomplete BIE evidence loop")
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"))
    prediction_id = hashlib.sha256(canonical.encode()).hexdigest()
    doc = _read_store(journal_path)
    if any(row["prediction_id"] == prediction_id for row in doc["predictions"]):
        raise ValueError("duplicate prediction")
    doc["predictions"].append({**packet, "prediction_id": prediction_id, "status": "open"})
    _write_store(journal_path, doc)
    return prediction_id


def resolve_prediction(prediction_id, *, outcome_up, observed_at_utc, source_ref, journal_path):
    if not isinstance(outcome_up, bool) or not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError("invalid outcome")
    observed = _time(observed_at_utc)
    doc = _read_store(journal_path)
    matches = [p for p in doc["predictions"] if p["prediction_id"] == prediction_id]
    if len(matches) != 1 or matches[0]["status"] != "open":
        raise ValueError("prediction missing or already resolved")
    prediction = matches[0]
    if observed <= _time(prediction["generated_at_utc"]):
        raise ValueError("outcome is not subsequent evidence")
    y = int(outcome_up)
    brier = (float(prediction["probability_up"]) - y) ** 2
    outcome = {"prediction_id": prediction_id, "outcome_up": outcome_up,
               "observed_at_utc": observed.isoformat(), "source_ref": source_ref,
               "brier_score": round(brier, 8)}
    doc["outcomes"].append(outcome)
    prediction["status"] = "resolved"
    _write_store(journal_path, doc)
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description="BIE prospective research journal; no broker writes")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest-quotes")
    ingest.add_argument("snapshot", type=Path)
    ingest.add_argument("--journal", type=Path, default=Path(".bie_runtime/market_evidence.json"))
    freeze = sub.add_parser("freeze-prediction")
    freeze.add_argument("packet", type=Path)
    freeze.add_argument("--journal", type=Path, default=Path(".bie_runtime/market_evidence.json"))
    args = parser.parse_args(argv)
    result = (ingest_quote_snapshot(args.snapshot, args.journal) if args.command == "ingest-quotes"
              else {"prediction_id": freeze_prediction(args.packet, args.journal)})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
