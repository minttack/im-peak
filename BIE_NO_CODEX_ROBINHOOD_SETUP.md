# Continue BIE Robinhood setup WITHOUT Codex

The owner has exhausted Codex usage. This repository can still be edited in ChatGPT through its connected GitHub integration. **Nothing here initiates a broker order.**

## Current verified state

- `run_bie.py` starts offline H139/H140 research only. It cannot authenticate to Robinhood or place orders.
- `BIE_RISK_POLICY.json` records a $20 total training budget and restricts live trading. Current live-orders and options flags stay **false**.
- `BIE_EMERGENCY_STOP.flag` is checked only by the standalone safety module, NOT by any unrelated Robinhood agent or platform.
- `BIE_20_OPTIONS_LEARNING_INTENT.json` documents the user's desire to learn with small real-money long-call/long-put trades (proposed <= $5 premium plus fees) and to keep external MCP Trade approvals OFF. It is a **preference**, not a verified brokerage setting or trading authorization.
- We have **no authenticated Robinhood Trading MCP tools in the current ChatGPT conversation**. A Codex connection does not give other apps, processes or ChatGPT access to its session.

## Connect to ChatGPT directly, if your account offers custom MCP plugins

Robinhood's [official external-agent onboarding](https://robinhood.com/us/en/support/articles/onboarding-an-external-agent/) lists:
1. In ChatGPT, go to Settings > Security & login and enable Developer Mode (if available).
2. Go to Plugins and select '+' to add a new custom plugin/connector.
3. Enter the official Robinhood Trading MCP URL: `https://agent.robinhood.com/mcp/trading`.
4. Complete authentication and, if prompted, open/confirm the dedicated Robinhood MCP account.

**Never paste passwords, 2FA codes, bearer tokens or API keys into ChatGPT messages or the public GitHub repository.** Features and menu availability can differ by account; if custom MCP setup isn't available, don't attempt insecure cookie extraction or unofficial API workarounds.

## Before any real-money purchase

Use the broker's authenticated tools to verify **which account** is tradeable, buying power, options level, fee-inclusive total premium, open/pending orders and Trade approvals status. Do not treat $20 in another wallet as proof it is available in the MCP account. If any check is missing, keep orders OFF. Robinhood's own [trading guide](https://robinhood.com/us/en/support/articles/trading-with-your-agent/) says MCP accounts normally default to Trade approvals OFF; no approval prompts may appear for eligible orders.

A custom ChatGPT MCP connection, even if installed, **does not automatically connect the local Windows BIE monitor**. The Windows runner would need its own supported, user-authorized integration, audited risk checks, idempotent submissions, and cancellation/emergency-stop coverage. A local stop flag is not a brokerage kill switch.

## Learning with a $20 budget

Strategy paper tests can be kept brief at the user's request, but execution safety checks cannot be skipped. Options may expire worthless, can have large spreads, and may expose the holder to special expiration or exercise risks. Restrict any future automation to long single-leg buy-to-open trades and explicitly price the 100-share contract multiplier plus fees; avoid margin, short options, auto-exercise surprises, and 0DTE. The proposed $5 maximum per contract is not a recommendation to spend it.

**Status: documented only, no live execution, no real orders, no active $20 brokerage-side limit.**
