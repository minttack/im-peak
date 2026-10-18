#!/usr/bin/env python3
"""BIE $20 PAPER-ONLY safety gate. No network, brokerage client, or order execution."""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY_FILE = ROOT / "BIE_RISK_POLICY.json"
STOP_FILE = ROOT / "BIE_EMERGENCY_STOP.flag"
FIELDS = ("starting_budget_usd", "daily_new_buy_limit_usd",
          "single_buy_limit_usd", "maximum_total_invested_usd")


def dollars(value):
    """Reject non-finite, negative, and nonnumeric money values (fail closed)."""
    if isinstance(value, bool) or value is None:
        raise ValueError("Money amount is missing or invalid")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Money amount is not numeric")
    if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
        raise ValueError("Money amount must be nonnegative USD cents")
    return n


def load_policy(path=POLICY_FILE):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise ValueError("Unsupported policy")
    for field in FIELDS:
        dollars(doc[field])
    if (doc.get("live_orders_enabled") is not False
            or doc.get("margin_enabled") is not False
            or doc.get("options_enabled") is not False
            or doc.get("short_selling_enabled") is not False):
        raise ValueError("Policy attempted to enable blocked live or high-risk features")
    if doc.get("robinhood_trade_approvals_preference") != "OFF":
        raise ValueError("Unexpected approval preference")
    if doc.get("paper_order_evaluation_enabled") is not True:
        raise ValueError("Paper evaluator is not enabled")
    if doc.get("permitted_assets") != ["stock", "etf"]:
        raise ValueError("Asset policy changed")
    age = doc.get("maximum_quote_age_seconds")
    if isinstance(age, bool) or not isinstance(age, int) or not 0 < age <= 120:
        raise ValueError("Quote freshness policy invalid")
    if (dollars(doc["daily_new_buy_limit_usd"]) >
        dollars(doc["starting_budget_usd"]) or
        dollars(doc["single_buy_limit_usd"]) >
        dollars(doc["daily_new_buy_limit_usd"]) or
        dollars(doc["maximum_total_invested_usd"]) >
        dollars(doc["starting_budget_usd"])):
        raise ValueError("Risk limits exceed budget")
    return doc


def live_order_allowed(*_args, **_kwargs):
    """Permanent fail-closed boundary in this research-only module."""
    return False


def assess_paper_buy(*, symbol, asset, notional_usd, available_cash_usd,
                     filled_buys_today_usd, pending_buys_today_usd,
                     existing_invested_usd, quote_age_seconds,
                     policy=None, stop_file=STOP_FILE):
    """Advisory simulation only; NEVER submits or reserves a real order.

    Inputs are caller supplied, not verified brokerage balances, positions,
    pending orders, or market quotes. Production integration would require
    authenticated reconciliation and atomic reservations, plus replay tests.
    """
    reasons = []
    if Path(stop_file).exists():
        reasons.append("EMERGENCY_STOP")
    try:
        p = load_policy() if policy is None else policy
        # Do not trust passed policy dictionaries.
        if not isinstance(p, dict) or p.get("live_orders_enabled") is not False:
            raise ValueError("Live-order policy invalid")
        if p.get("margin_enabled") is not False or p.get("options_enabled") is not False:
            raise ValueError("Restricted trading policy")
        if p.get("short_selling_enabled") is not False:
            raise ValueError("Short-selling policy")
        if not p.get("paper_order_evaluation_enabled"):
            raise ValueError("Paper mode disabled")
        if p.get("permitted_assets") != ["stock", "etf"]:
            raise ValueError("Asset policy invalid")
        if (dollars(p["daily_new_buy_limit_usd"]) >
            dollars(p["starting_budget_usd"]) or
            dollars(p["single_buy_limit_usd"]) >
            dollars(p["daily_new_buy_limit_usd"])):
            raise ValueError("Invalid budget hierarchy")
        values = {k: dollars(v) for k, v in {
            "notional": notional_usd, "cash": available_cash_usd,
            "filled": filled_buys_today_usd, "pending": pending_buys_today_usd,
            "invested": existing_invested_usd}.items()}
        if isinstance(quote_age_seconds, bool) or not isinstance(quote_age_seconds, (int, float)) or quote_age_seconds < 0 or quote_age_seconds > p["maximum_quote_age_seconds"]:
            reasons.append("STALE_OR_INVALID_QUOTE")
        if not isinstance(symbol, str) or not symbol.isascii() or not symbol.isupper() or not (1 <= len(symbol) <= 8) or not symbol.replace(".", "").isalnum():
            reasons.append("INVALID_SYMBOL")
        if asset not in ("stock", "etf"):
            reasons.append("ASSET_NOT_ALLOWED")
        if values["notional"] == 0:
            reasons.append("ZERO_ORDER")
        if values["notional"] > dollars(p["single_buy_limit_usd"]):
            reasons.append("OVER_SINGLE_BUY_LIMIT")
        if values["filled"] + values["pending"] + values["notional"] > dollars(p["daily_new_buy_limit_usd"]):
            reasons.append("OVER_DAILY_BUY_LIMIT")
        if values["notional"] > values["cash"]:
            reasons.append("INSUFFICIENT_CASH")
        if values["invested"] + values["pending"] + values["notional"] > dollars(p["maximum_total_invested_usd"]):
            reasons.append("OVER_TOTAL_INVESTED_LIMIT")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        reasons.append("INVALID_OR_MISSING_POLICY_OR_INPUT")
    return {"paper_candidate_allowed": not reasons, "live_order_allowed": False,
            "reasons": reasons, "submitted_orders": 0}


def main():
    parser = argparse.ArgumentParser(description="BIE PAPER-ONLY spending controls; no Robinhood access")
    parser.add_argument("command", choices=("status", "stop", "paper-demo"))
    args = parser.parse_args()
    if args.command == "stop":
        STOP_FILE.write_text("STOP: operator requested emergency stop.\n", encoding="utf-8")
        print("EMERGENCY STOP LATCHED. No live trades possible through this module.")
        return 0
    print("BIE $20 SAFETY GATE | Robinhood orders: DISABLED | separate MCP agent: NOT CONNECTED")
    try:
        p = load_policy()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print("POLICY INVALID: all requests denied; problem must be fixed manually.")
        return 2
    print("Daily new-buy cap: $" + p["daily_new_buy_limit_usd"] +
          " | Per-order cap: $" + p["single_buy_limit_usd"] +
          " | Total investment cap: $" + p["maximum_total_invested_usd"])
    print("Emergency stop: " + ("ON (latched)" if STOP_FILE.exists() else "OFF (paper evaluation only)"))
    if args.command == "paper-demo":
        print(json.dumps(assess_paper_buy(
            symbol="SPY", asset="etf", notional_usd="1.00",
            available_cash_usd="20.00", filled_buys_today_usd="0.00",
            pending_buys_today_usd="0.00", existing_invested_usd="0.00",
            quote_age_seconds=10), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
