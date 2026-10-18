"""Non-operational order boundary for future reviewed integration.

There is intentionally no MCP session, endpoint, or tool name in this module.
"""
from pathlib import Path

from bie_options_safety import STOP_FILE, assess_proposal


class OrderSubmissionDisabled(RuntimeError):
    pass


def prepare_exact_option_proposal(*, account, contract, now=None, stop_file=STOP_FILE):
    """Return the exact review packet after all read-only inputs are supplied."""
    result = assess_proposal(account=account, contract=contract, now=now, stop_file=stop_file)
    return {"integration_stage": result["stage"], "exact_contract": dict(contract),
            "safety": result, "submission_supported": False, "orders_submitted": 0}


def submit_order(*_args, **_kwargs):
    """Permanent boundary until a separately reviewed implementation replaces it."""
    raise OrderSubmissionDisabled("Live order submission is not implemented or enabled")


def emergency_stop_latched(stop_file=STOP_FILE):
    return Path(stop_file).exists()
