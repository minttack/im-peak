#!/usr/bin/env python3
"""Fail-closed, proposal-only safety checks for tiny long-option experiments.

This module has no broker client and no order-submission function. Caller-supplied
account and quote data must first be obtained through authenticated read-only
broker tools. The repository emergency stop remains an independent hard block.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY_FILE = ROOT / "BIE_OPTIONS_PROPOSAL_POLICY.json"
STOP_FILE = ROOT / "BIE_EMERGENCY_STOP.flag"


def money(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("invalid money")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid money") from None
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValueError("money must be nonnegative USD cents")
    return amount


def load_policy(path=POLICY_FILE):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if policy.get("schema") != 1:
        raise ValueError("unsupported policy")
    if policy.get("live_orders_enabled") is not False or policy.get("options_enabled") is not False:
        raise ValueError("proposal policy attempted to enable trading")
    for field in ("maximum_account_risk_usd", "maximum_new_debit_per_day_usd",
                  "maximum_single_debit_usd"):
        money(policy[field])
    if money(policy["maximum_single_debit_usd"]) > money(policy["maximum_new_debit_per_day_usd"]):
        raise ValueError("single debit exceeds daily cap")
    if money(policy["maximum_new_debit_per_day_usd"]) > money(policy["maximum_account_risk_usd"]):
        raise ValueError("daily debit exceeds account cap")
    if policy.get("allowed_action") != "BUY_TO_OPEN" or policy.get("allowed_quantity") != 1:
        raise ValueError("unsafe option shape")
    if policy.get("allowed_multiplier") != 100 or policy.get("allowed_option_types") != ["call", "put"]:
        raise ValueError("unsafe option contract policy")
    if not 0 < policy.get("maximum_quote_age_seconds", 0) <= 120:
        raise ValueError("invalid quote age")
    return policy


def live_order_allowed(*_args, **_kwargs):
    """There is deliberately no path from this module to a live order."""
    return False


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def assess_proposal(*, account, contract, now=None, policy=None, stop_file=STOP_FILE):
    """Assess an exact option proposal using verified, read-only broker observations."""
    reasons = []
    details = {}
    try:
        p = load_policy() if policy is None else policy
        # Re-validate passed policies rather than trusting a caller to enable trading.
        if p.get("live_orders_enabled") is not False or p.get("options_enabled") is not False:
            raise ValueError("trading enabled")
        current = _utc(now or datetime.now(timezone.utc).isoformat())

        required_truths = ("authenticated", "dedicated_agentic_account", "options_eligible",
                           "buying_power_verified", "holdings_verified", "open_orders_verified",
                           "approval_status_verified")
        for field in required_truths:
            if account.get(field) is not True:
                reasons.append("ACCOUNT_" + field.upper() + "_MISSING")

        cash = money(account["available_buying_power_usd"])
        existing = money(account["existing_option_risk_usd"])
        pending = money(account["pending_option_commitments_usd"])
        today = money(account["new_option_debits_today_usd"])
        bid = money(contract["bid_usd"])
        ask = money(contract["ask_usd"])
        limit = money(contract["limit_price_usd"])
        fees = money(contract["estimated_fees_usd"])

        if contract.get("action") != p["allowed_action"]:
            reasons.append("ACTION_NOT_ALLOWED")
        if contract.get("quantity") != p["allowed_quantity"]:
            reasons.append("QUANTITY_NOT_ALLOWED")
        if contract.get("multiplier") != p["allowed_multiplier"]:
            reasons.append("MULTIPLIER_NOT_ALLOWED")
        if contract.get("option_type") not in p["allowed_option_types"]:
            reasons.append("OPTION_TYPE_NOT_ALLOWED")
        symbol = contract.get("symbol")
        if not isinstance(symbol, str) or not symbol.isascii() or not symbol.isupper() or not symbol.isalnum():
            reasons.append("INVALID_SYMBOL")
        if bid <= 0 or ask < bid or limit <= 0 or limit > ask:
            reasons.append("INVALID_OR_UNMARKETABLE_PRICE")
        else:
            midpoint = (bid + ask) / 2
            if (ask - bid) / midpoint > Decimal(str(p["maximum_bid_ask_spread_fraction"])):
                reasons.append("SPREAD_TOO_WIDE")

        quote_age = (current - _utc(contract["quote_timestamp"])).total_seconds()
        if quote_age < 0 or quote_age > p["maximum_quote_age_seconds"]:
            reasons.append("STALE_OR_FUTURE_QUOTE")
        expiry = date.fromisoformat(contract["expiration"])
        if (expiry - current.date()).days < p["minimum_days_to_expiration"]:
            reasons.append("ZERO_DTE_OR_EXPIRED")

        all_in = limit * Decimal(contract["multiplier"]) * Decimal(contract["quantity"]) + fees
        details["maximum_debit_usd"] = f"{all_in:.2f}"
        if all_in > money(p["maximum_single_debit_usd"]):
            reasons.append("OVER_SINGLE_DEBIT_LIMIT")
        if today + pending + all_in > money(p["maximum_new_debit_per_day_usd"]):
            reasons.append("OVER_DAILY_DEBIT_LIMIT")
        if existing + pending + all_in > money(p["maximum_account_risk_usd"]):
            reasons.append("OVER_ACCOUNT_RISK_LIMIT")
        if all_in > cash:
            reasons.append("INSUFFICIENT_BUYING_POWER")
        canonical = json.dumps({"contract": contract, "maximum_debit_usd": details["maximum_debit_usd"]},
                               sort_keys=True, separators=(",", ":"))
        details["idempotency_key"] = hashlib.sha256(canonical.encode()).hexdigest()
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError, InvalidOperation):
        reasons.append("INVALID_OR_MISSING_VERIFIED_INPUT")

    prerequisites_pass = not reasons
    if Path(stop_file).exists():
        reasons.append("EMERGENCY_STOP_LATCHED")
    return {
        "stage": "PROPOSAL_READY" if not reasons else "CONNECTED_READONLY",
        "proposal_ready": not reasons,
        "prerequisites_pass_before_stop": prerequisites_pass,
        "live_order_allowed": False,
        "submitted_orders": 0,
        "reasons": reasons,
        **details,
    }


class ReservationLedger:
    """Atomic local proposal reservations; broker reconciliation is mandatory."""

    def __init__(self, path):
        self.path = Path(path)

    def _read(self):
        if not self.path.exists():
            return {"schema": 1, "reservations": {}}
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if doc.get("schema") != 1 or not isinstance(doc.get("reservations"), dict):
            raise ValueError("invalid ledger")
        return doc

    def _write(self, doc):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)

    def reserve(self, assessment):
        if assessment.get("proposal_ready") is not True or assessment.get("live_order_allowed") is not False:
            raise ValueError("proposal is not safely reviewable")
        key = assessment["idempotency_key"]
        doc = self._read()
        if key in doc["reservations"]:
            raise ValueError("duplicate proposal")
        doc["reservations"][key] = {"maximum_debit_usd": assessment["maximum_debit_usd"],
                                     "status": "reserved"}
        self._write(doc)
        return key

    def reconcile(self, key, *, broker_status, broker_open_orders_verified):
        if broker_open_orders_verified is not True:
            raise ValueError("broker open orders were not verified")
        if broker_status not in ("reserved", "open", "partially_filled", "filled", "rejected", "cancelled"):
            raise ValueError("unknown broker status")
        doc = self._read()
        if key not in doc["reservations"]:
            raise ValueError("unknown reservation")
        doc["reservations"][key]["status"] = broker_status
        self._write(doc)

