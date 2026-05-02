"""Run the Application UI WebSocket server as ``python -m openharness.web``.

This bypasses the top-level ``oh`` CLI so it works even when the repo
hasn't been installed editable (useful for development when another
OpenHarness package is shadowing this one).

Usage::

    PYTHONPATH=src python -m openharness.web --port 8765
"""

from __future__ import annotations

import argparse

from openharness.web.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m openharness.web",
        description="HTTP + WebSocket backend for frontend/application-ui (WS /ws, API /api/*).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", dest="base_url", default=None)
    parser.add_argument("--api-key", dest="api_key", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--system-prompt", dest="system_prompt", default=None)
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        provider=args.provider,
        system_prompt=args.system_prompt,
    )


if __name__ == "__main__":
    main()
