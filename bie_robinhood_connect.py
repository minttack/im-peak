#!/usr/bin/env python3
"""Optional Robinhood Trading MCP connection for BIE: READ-ONLY quote snapshots.

This separate process never has an order sender. It calls only the exact,
allowlisted get_equity_quotes tool after interactive browser OAuth.
Do not interpret snapshots as validated trading signals.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse
import webbrowser

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".bie_runtime"
STATUS = RUNTIME / "robinhood_connection_status.json"
SNAPSHOT = RUNTIME / "robinhood_quotes_latest.json"
SERVER = "https://agent.robinhood.com/mcp/trading"
CALLBACK_PORT = 3030
DEFAULT_SYMBOLS = ("MSFT", "META", "XOM", "AMZN", "JNJ", "SPY", "QQQ")
QUOTE_TOOL = "get_equity_quotes"
# No brokerage-trading tool can be called from this module.
READ_ONLY_ALLOWLIST = frozenset((QUOTE_TOOL,))


def write_json(path: Path, data: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def status(state: str, detail: str = "") -> None:
    write_json(STATUS, {
        "state": state,
        "updated_utc": now(),
        "details": detail,
        "live_orders_enabled": False,
        "connection_type": "separate read-only OAuth session",
        "model_integration": "raw quote snapshot only; no H140 prediction hook",
    })
    print(f"BIE ROBINHOOD: {state} {detail}", flush=True)


def _schema_variants(spec: dict) -> list[dict]:
    """Expand JSON-Schema nullable unions; never guess parameter names."""
    if not isinstance(spec, dict):
        return []
    variants = [spec]
    for key in ("anyOf", "oneOf"):
        values = spec.get(key)
        if isinstance(values, list):
            variants.extend(item for item in values if isinstance(item, dict))
    # A nullable union can also use type: ["array", "null"].
    types = spec.get("type")
    if isinstance(types, list) and "array" in types:
        variants.append({**spec, "type": "array"})
    if isinstance(types, list) and "string" in types:
        variants.append({**spec, "type": "string"})
    return variants


def quote_arguments(input_schema: dict, symbols: tuple[str, ...]) -> dict | None:
    """Accept simple & nullable JSON schema formats for READ-ONLY quote calls."""
    if not isinstance(input_schema, dict):
        return None
    props = input_schema.get("properties")
    required = input_schema.get("required", [])
    if not isinstance(props, dict) or not isinstance(required, list):
        return None
    if not symbols or len(symbols) > 20:
        return None
    # Only the public quote field is supported. Reject any additional required
    # arguments, including account numbers, to avoid malformed requests.
    if any(field not in ("symbols", "tickers", "symbol", "ticker")
           for field in required):
        return None
    for name in ("symbols", "tickers", "symbol", "ticker"):
        spec = props.get(name)
        if not isinstance(spec, dict):
            continue
        if any(field != name for field in required):
            continue
        for candidate in _schema_variants(spec):
            if name in ("symbols", "tickers") and candidate.get("type") == "array":
                items = candidate.get("items")
                if not isinstance(items, dict):
                    continue
                if any(item.get("type") == "string" for item in _schema_variants(items)):
                    return {name: list(symbols)}
            elif name in ("symbol", "ticker") and candidate.get("type") == "string":
                return {name: symbols[0]}
    return None


def safe_quote_schema_diagnostic(input_schema: dict) -> dict:
    """Show the shape of a tool's *public parameter schema*, never account data."""
    if not isinstance(input_schema, dict):
        return {"schema_shape": "non-object"}
    props = input_schema.get("properties", {})
    if not isinstance(props, dict):
        return {"schema_shape": "no-properties"}
    result = {
        "fields": sorted(str(k) for k in props)[:15],
        "required": sorted(str(k) for k in input_schema.get("required", [])
                           if isinstance(k, str))[:15]
                    if isinstance(input_schema.get("required", []), list) else "unknown",
    }
    for name in ("symbols", "tickers", "symbol", "ticker"):
        spec = props.get(name)
        if isinstance(spec, dict):
            result[name + "_types"] = [
                str(v.get("type", "unknown")) for v in _schema_variants(spec)
            ][:8]
            break
    return result


class MemoryTokens:
    """Token implementation created lazily to avoid SDK import during unit tests."""

    @staticmethod
    def build():
        from mcp.client.auth import TokenStorage

        class Storage(TokenStorage):
            def __init__(self):
                self._tokens = None
                self._client_info = None

            async def get_tokens(self):
                return self._tokens

            async def set_tokens(self, tokens):
                self._tokens = tokens

            async def get_client_info(self):
                return self._client_info

            async def set_client_info(self, info):
                self._client_info = info

        return Storage()


class BrowserCallback:
    def __init__(self):
        self.result: dict = {}
        self.done = threading.Event()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parts = urlparse(self.path)
                if parts.path != "/callback":
                    self.send_error(404)
                    return
                query = parse_qs(parts.query)
                for key in ("code", "state", "error"):
                    if key in query and query[key]:
                        outer.result[key] = query[key][0]
                outer.done.set()
                self.send_response(200 if "code" in outer.result else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"Robinhood authorization response received. Return to BIE."
                )

            def log_message(self, fmt, *args):
                return

        # Bind to local loopback only; not a network-facing web service.
        self.server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.worker.start()

    async def wait(self):
        accepted = await asyncio.to_thread(self.done.wait, 300)
        if not accepted:
            raise TimeoutError("Robinhood authorization was not finished in five minutes")
        if "error" in self.result:
            raise RuntimeError("Robinhood denied authorization")
        code = self.result.get("code")
        if not code:
            raise RuntimeError("No OAuth authorization code returned")
        return code, self.result.get("state")

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)


async def connect(symbols: tuple[str, ...], watch: bool) -> None:
    try:
        from mcp.client.auth import OAuthClientProvider
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.shared.auth import OAuthClientMetadata
    except ImportError as exc:
        raise RuntimeError("Missing MCP SDK. Run CONNECT_BIE_ROBINHOOD_READONLY.bat") from exc

    cb = BrowserCallback()
    cb.start()
    async def show_login(url: str) -> None:
        print("Opening your browser for Robinhood login. Sign in yourself.")
        if not webbrowser.open(url):
            print("Could not open browser automatically; check default Windows browser.")

    async def finish_login():
        print("Waiting for Robinhood browser authorization (up to 5 minutes)...")
        return await cb.wait()

    try:
        auth = OAuthClientProvider(
            server_url=SERVER,
            client_metadata=OAuthClientMetadata.model_validate({
                "client_name": "BIE Research Read Only",
                "redirect_uris": [f"http://localhost:{CALLBACK_PORT}/callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            }),
            storage=MemoryTokens.build(),
            redirect_handler=show_login,
            callback_handler=finish_login,
        )
        status("CONNECTING", "No Robinhood orders permitted")
        async with streamablehttp_client(
            url=SERVER, auth=auth, timeout=timedelta(seconds=60)
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                catalog = await session.list_tools()
                tools = {tool.name: tool for tool in catalog.tools}
                status("CONNECTED_READONLY", f"MCP authenticated; {len(tools)} tool names discovered")
                print(f"Robinhood catalog contains equity quotes: {QUOTE_TOOL in tools}")
                print("NO orders. No account funds accessed for trades.")
                if not watch:
                    status("CONNECTION_TEST_PASSED", "Session closed after safe tool discovery")
                    return
                while True:
                    quote = tools.get(QUOTE_TOOL)
                    args = quote_arguments(quote.inputSchema, symbols) if quote else None
                    if args is None or QUOTE_TOOL not in READ_ONLY_ALLOWLIST:
                        status("READONLY_WAITING", "Quote input schema not recognized; no calls made")
                        if quote:
                            print("Quote parameter schema shape (no account info):",
                                  json.dumps(safe_quote_schema_diagnostic(quote.inputSchema)),
                                  flush=True)
                        await asyncio.sleep(300)
                        continue
                    try:
                        # HARDCODED exact quote tool; never invoke place_* or cancel_*.
                        result = await session.call_tool(QUOTE_TOOL, args)
                        if result.isError:
                            status("READONLY_WAITING", "Robinhood quote request returned an error")
                        else:
                            write_json(SNAPSHOT, {
                                "source": "Robinhood Trading MCP",
                                "received_at_utc": now(),
                                "requested_symbols": list(symbols),
                                "raw_quote_response": result.model_dump(mode="json"),
                                "warning": "Timestamp is receipt time; quotes may be delayed or stale. Research-only data, no orders.",
                            })
                            status("CONNECTED_READONLY", f"Quote snapshot saved to {SNAPSHOT}")
                    except Exception:
                        status("READONLY_WAITING", "Quote request failed; check connection")
                    await asyncio.sleep(300)
    finally:
        cb.close()


def symbols_from_text(value: str) -> tuple[str, ...]:
    symbols = tuple(s.strip().upper() for s in value.split(","))
    if not symbols or len(symbols) > 10 or any(
        not s or not s.isascii() or not s.replace(".", "").isalpha() or len(s) > 8
        for s in symbols
    ):
        raise ValueError("Use 1-10 standard comma-separated stock/ETF tickers")
    return symbols


def main():
    parser = argparse.ArgumentParser(description="BIE Robinhood read-only OAuth + quotes; never sends orders")
    parser.add_argument("--once", action="store_true", help="Only verify MCP OAuth/tools, then exit")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    args = parser.parse_args()
    try:
        tickers = symbols_from_text(args.symbols)
        asyncio.run(connect(tickers, watch=not args.once))
        if not args.once:
            status("DISCONNECTED", "Stopped normally")
    except KeyboardInterrupt:
        status("STOPPED", "User requested stop")
    except Exception as exc:
        # Don't dump exception strings: network exceptions may contain OAuth URLs/tokens.
        status("CONNECTION_FAILED", type(exc).__name__)
        print("Unable to verify Robinhood OAuth connection. No orders were attempted.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
