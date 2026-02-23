"""Thread-safe wrapper around the async MCP stdio client.

The MCP SDK is fully async. Streamlit runs synchronously in the main thread.
This module bridges the gap by running the MCP session in a background thread
that owns a dedicated asyncio event loop, and exposing a simple synchronous API
to the Streamlit app.
"""

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

_STREAMLIT_UI_DIR = Path(__file__).parent.resolve()


class MCPToolInfo:
    """Lightweight descriptor for an MCP tool (mirrors mcp.types.Tool)."""

    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_openai_function(self) -> dict:
        """Return the OpenAI function-calling representation of this tool."""
        params = self.input_schema or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or "",
                "parameters": params,
            },
        }


class MCPClient:
    """Synchronous facade over an async MCP stdio session.

    Usage
    -----
    client = MCPClient(env={"PATHWAYS_API_TOKEN": "..."})
    # client.tools  → list[MCPToolInfo]
    # client.call_tool("list_segmentations", {})  → str
    # client.shutdown()
    """

    def __init__(self, env: dict[str, str] | None = None):
        self._env = env or {}
        self._tools: list[MCPToolInfo] = []
        self._session: ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._initialized = threading.Event()
        self._init_error: Exception | None = None

        self._thread = threading.Thread(
            target=self._thread_main, name="mcp-session", daemon=True
        )
        self._thread.start()

        # Wait up to 30 s for the MCP server to start and initialise
        if not self._initialized.wait(timeout=60):
            raise RuntimeError(
                "MCP server did not initialise within 60 s. "
                "Check PATHWAYS_API_TOKEN and server logs."
            )
        if self._init_error:
            raise self._init_error

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_session())
        except Exception as exc:
            if not self._initialized.is_set():
                self._init_error = exc
                self._initialized.set()
        finally:
            self._loop.close()

    async def _run_session(self):
        merged_env = {**os.environ, **self._env}

        params = StdioServerParameters(
            command=sys.executable,
            args=[str(_STREAMLIT_UI_DIR / "run_server.py")],
            env=merged_env,
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                self._tools = [
                    MCPToolInfo(
                        name=t.name,
                        description=t.description or "",
                        input_schema=t.inputSchema or {},
                    )
                    for t in tools_result.tools
                ]

                self._session = session
                self._stop_event = asyncio.Event()
                self._initialized.set()  # Signal that we're ready

                # Stay alive until shutdown() is called
                await self._stop_event.wait()

    # ------------------------------------------------------------------
    # Public synchronous API
    # ------------------------------------------------------------------

    @property
    def tools(self) -> list[MCPToolInfo]:
        return self._tools

    def get_openai_tools(self) -> list[dict]:
        return [t.to_openai_function() for t in self._tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Synchronously call an MCP tool and return its text result."""
        if self._session is None or self._loop is None:
            raise RuntimeError("MCP client is not initialised.")

        async def _call():
            result = await self._session.call_tool(name, arguments)  # type: ignore[union-attr]
            parts: list[str] = []
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    parts.append(content_item.text)
            return "\n".join(parts) if parts else ""

        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        try:
            return future.result(timeout=120)
        except Exception as exc:
            logger.error("Tool call %r failed: %s", name, exc)
            return json.dumps({"error": str(exc)})

    def shutdown(self):
        """Signal the background thread to exit cleanly."""
        if self._stop_event and self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._thread.join(timeout=5)
