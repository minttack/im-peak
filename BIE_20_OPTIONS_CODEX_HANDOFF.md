# BIE / Robinhood MCP — $20 small-options learning intent

The user has explicitly asked to prepare autonomous trading within a total **$20** budget, including small **long-options** trades, and prefers Robinhood trade approvals **OFF**. They want to skip extended *strategy paper trading*, but **not** correctness, permissions, or safety checks.

## Current verified repository status
- GitHub BIE H140 launcher is **offline research only**; the H140 strategy isn't validated to select profitable live orders.
- Existing `BIE_RISK_POLICY.json` has `live_orders_enabled=false`, `options_enabled=false`; **do not silently edit those controls**.
- Existing `BIE_EMERGENCY_STOP.flag` is **latched**. It affects only code that explicitly checks it; it is NOT a Robinhood-side emergency stop or order cancellation.
- No Robinhood credentials or brokerage tools are available to this ChatGPT session. Codex may have its **own** separately authorized Robinhood Trading MCP connection.
- User says they have only $20 overall; this does **not** prove any Robinhood MCP account has $20 settled, available buying power or that trading with it is affordable.

## What Codex should do with its OWN authenticated Robinhood Trading MCP connection
1. Verify MCP tool authentication. Read account list, dedicated MCP trading account, available buying power, existing holdings, open orders, options eligibility, and trade-approval setting **from Robinhood**, not from a text assertion. If any required tool unavailable, stop and report blocker. Don't access a normal personal Robinhood investing account for order placement.
2. **Never** fund or transfer money automatically; don't buy or sell anything simply because this instruction file is read. Ask user to confirm the dedicated trading funds are available.
3. Prepare an **account-level $20 maximum** total capital-at-risk protection. As a proposed conservative implementation while balance is small, cap each new premium-plus-fees at $5, new buys per trading day at $5, and include filled, pending, and still-open order commitments. Reconcile current cost basis/positions to avoid treating previously spent money as free. These are maximum ceilings, not required spending targets.
4. Options may only be single-leg **BUY_TO_OPEN 1 long call or long put**, limit priced, with all-in premium including 100-share multiplier and estimated fees **<= $5**. No margin borrowing, uncovered calls/puts, spreads, short selling, 0DTE or auto-roll. Reject illiquid/stale/missing quotes and unsuitable expirations. The user must have the required options level.
5. Check for all-in cash affordability, contract multiplier, strike, expiry, quote timestamp, fees, lot size, pending orders, and cash/position constraints before proposing an order; reject invalid or unavailable data. Do not infer options tradability from equity access.
6. Implement a local HARD STOP checked in every order code path, startup fails closed, durable daily counters, order-reservation & idempotency keys, after-crash reconciliation, broker open-order checks, broker-side cancellation/disconnect procedure, and audit logs. A stop file alone is not enough to control other agents.
7. Run **software safety tests** for duplicate submissions, partial fills, stale quotes, rejected orders, insufficient cash, fee/multiplier errors, crashes and restarts. User may skip long strategy backtests; do NOT skip execution correctness/safety verification.
8. Do NOT remove `BIE_EMERGENCY_STOP.flag`, turn on `live_orders_enabled`, or submit a real order unless all prerequisites demonstrably pass AND the user gives clear final permission after seeing the precise symbol, contract, expiry, strike, maximum debit, and any unverified information. Keep maximum dollar exposure bounded across bot restarts.
9. Trade approvals OFF is the user's **preference**, not a setting this repository can change. User handles it inside Robinhood Agent Settings. Never misrepresent its status. Certain orders may still require Robinhood confirmation.
10. Report the exact integration stage: NOT_CONNECTED, CONNECTED_READONLY, PROPOSAL_READY, or VERIFIED_ORDER_PLACED. Only Robinhood acknowledgment qualifies as placed. Preserve H140 and H141 research sources unchanged.

## For the user
Options can lose 100% of their premium. Extremely cheap options are often illiquid or highly speculative. **Nothing in this file activates trading or spends $20.** An externally authorized Robinhood agent can act independently if trade approvals are off; monitor its activity carefully.
