# BIE offline research launcher

1. Download or clone this repo to Windows. Install Python 3.10 or newer.
2. Leave either `BIE_H140_REAL_MARKET_ROBUSTNESS_CODEX_20261017.zip` or `BIE_H139_OPTIMIZED_CODEX_CORE_UNDER_25MB.zip` beside this script. H140 is preferred if available.
3. Double-click `RUN_BIE_H140.bat` (or run `python run_bie.py`). It extracts the ZIP into `.bie_runtime/extracted`, runs the H139/H140 focused tests, and runs a **synthetic** Flood Movement demo.
4. If H140 has incompatibilities, the script reports failure instead of claiming it worked. `python run_bie.py --archive BIE_H139_OPTIMIZED_CODEX_CORE_UNDER_25MB.zip` explicitly tests H139.
5. This is not an autonomous service; no live stock prices, authenticated Robinhood account, brokerage orders, or profitability proof. For additional tests: `python run_bie.py --full-tests` (may time out).

**Verified in an independent Linux test of the H139 ZIP:** 30/30 focused tests passed and the synthetic flow demo ran with `broker_orders` absent from the source report but no brokerage integration was invoked. H139's lean ZIP lacks an optional original vendor archive; full integrity verification is not claimed. The GitHub H140 archive has **not** been executed in this environment: GitHub file access does not currently provide the binary bytes. Run it locally to establish its status.
