"""Minimal WebSocket backend for the Application UI.

This package implements just enough of the OpenHarness frontend protocol
(`src/openharness/ui/protocol.py` equivalents) to support plain chat — no
tool calls, no session persistence, no permission flow yet.

See `server.py` for the runnable entry point (``oh web``).
"""

from openharness.web.server import ServerConfig, run_server

__all__ = ["ServerConfig", "run_server"]
