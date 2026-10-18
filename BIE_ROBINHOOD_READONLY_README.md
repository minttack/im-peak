# BIE ↔ Robinhood Trading MCP (READ-ONLY connection prototype)

This is an **optional new component** added without modifying or replacing
H139/H140 BIE source ZIPs, the existing local BIE monitor, or the $20 risk
policy. It is NOT a trading bot and has not yet been authorized on your PC.

## Get started on Windows (without Codex)
1. Download the updated repository, or copy these two files to your existing
   im-peak-main folder, alongside run_bie.py:
   - bie_robinhood_connect.py
   - CONNECT_BIE_ROBINHOOD_READONLY.bat
2. Double-click CONNECT_BIE_ROBINHOOD_READONLY.bat. It creates an **isolated
   Python environment** under .bie_runtime and installs the official
   Model Context Protocol Python SDK pinned to 1.23.0.
3. Follow the Robinhood authorization page **on your own Windows browser**.
   Your already-connected Codex agent does not transfer its credentials.
4. Leave the terminal window open to try quote requests at 5-minute
   intervals. Ctrl+C stops this prototype.

If the OAuth step rejects unknown clients, gives a browser error, or cannot
connect, it stops and reports an error without placing orders. Robinhood may
require a different client registration flow; the connector is NOT verified
against live Robinhood servers in this development environment.

## What this connector actually does
- Connects to **https://agent.robinhood.com/mcp/trading** through the
  standard MCP OAuth Streamable HTTP transport.
- Authorizes on the user's own device via a short-lived localhost callback.
  OAuth access tokens live in memory only and are **never saved or sent to GitHub**.
- Lists available tools (no tool calls, no orders) after authentication.
- During watch mode, calls ONLY **get_equity_quotes**, if its discovered
  input schema can be safely inferred, for up to 7 default symbols.
- Writes raw quote snapshots to
  **.bie_runtime/robinhood_quotes_latest.json**; writes connection state
  to **.bie_runtime/robinhood_connection_status.json**.
- The raw response remains in `robinhood_quotes_latest.json`. A separate
  prospective evidence bridge normalizes explicit symbol/price fields into
  `.bie_runtime/market_evidence.json`, preserves the raw snapshot SHA-256,
  provider and receipt timestamps, missing symbols, and freshness warnings.
- Point-in-time quotes are never relabeled as completed daily OHLCV. H140 model
  fitting still requires reviewed daily history through its existing importer.
- A prediction can be frozen only from a BIE H140 prediction packet labeled
  `NO_TRADE_RESEARCH`; a later timestamped observation resolves its Brier score.
- No options orders, stock orders, cash moves, or trade approvals changes.
  No credentials are stored. It may prompt OAuth each start.
- It is a standalone prototype: no unattended restart, no permanent
  background authorization, no guarantee of feed completeness.
- The emergency-stop flag for the existing safety policy **does NOT
  stop Codex or any other separate connected agent**.

## Diagnostic command
py -3 bie_robinhood_connect.py --once

This requires the MCP SDK to be installed in the current Python environment.
Running the .bat file installs it privately and handles setup for you.

## Security and next phases
Do not share passwords, OAuth codes, tokens, or account numbers in screenshots.
Trade approvals OFF means **other authorized external agents** may place
eligible real trades without each-order approval. This connector never sends
orders but cannot disable or stop those other agents.

The quote evidence bridge and disabled execution boundary are covered by the
offline regression suite. Real trades still require freshly verified options
eligibility, buying power, positions, pending orders, approval status, and a
separately reviewed order-capable implementation. With only $20, small options
could still lose all premium quickly. No promises of profit.
