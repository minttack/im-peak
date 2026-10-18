# BIE 20-dollar safety configuration (proposal, PAPER-ONLY)

This is an additive guard module for future integration. It does not modify the
existing H139/H140 ZIP, the research monitor, H141, or your Windows installation.

**Configuration:** $20 starting budget, $2 maximum *new buys per day*,
$2 maximum individual new buy, $20 maximum total invested, and no margin,
short sales, or options. The daily cap includes already filled **plus pending**
buy notional. Available cash and current invested notional must be reconciled
from authenticated account data before any real order is considered.

**Trade approvals preference:** OFF (as requested), *not set via this code*.
Turning Robinhood approvals OFF can let an external MCP agent place eligible
orders without confirming each one. Only you can manage your Robinhood
Agentic/MCP account. These settings do not protect any other external agent.

**HARD STOP:** This repository ships with `BIE_EMERGENCY_STOP.flag` present.
`BIE_EMERGENCY_STOP.bat` creates/latches that flag again. The new paper
evaluator checks it. It does **NOT** cancel brokerage orders, disconnect a
Robinhood agent, or stop a different program that does not call this gate.
To halt an actual agent, pause/disconnect that agent inside Robinhood as well.

**Live execution:** DISABLED. This code contains NO Robinhood API access, no
broker order sender, no credentials, and no background scheduler. Even a
passing paper evaluation is **not** approval to submit an order. Approval
preference and order permissions are separate from these offline checks.

To inspect: double-click `BIE_CHECK_SAFETY.bat` or use
`py -3 bie_safety.py status`. To test: `py -3 -m unittest tests.test_bie_safety -v`.
To latch the stop: double-click `BIE_EMERGENCY_STOP.bat`.

To safely implement **future live execution**, first verify agentic account
onboarding, account-specific buying power and position/order data, obtain
up-to-date market data, reconcile filled and still-open orders, persist atomic
order reservations across crashes/restarts, prevent duplicate submissions,
ensure each order path checks stop state and risk policy, provide a separate
brokerage order-cancel/pause/disconnect capability, and validate in paper
trading + independent replay. None of this is accomplished by turning Trade
approvals OFF. Never commit login secrets or API tokens into GitHub.
