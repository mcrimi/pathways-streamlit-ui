"""Thread-safe wrapper around the async MCP streamable HTTP client.

The MCP SDK is fully async. Streamlit runs synchronously in the main thread.
This module bridges the gap by running the MCP session in a background thread
that owns a dedicated asyncio event loop, and exposing a simple synchronous API
to the Streamlit app.
"""

import asyncio
import json
import logging
import threading
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import AnyUrl

logger = logging.getLogger(__name__)

REMOTE_MCP_URL = "https://pathways.fastmcp.app/mcp"


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


class MCPPromptInfo:
    """Lightweight descriptor for an MCP prompt."""

    def __init__(self, name: str, description: str, arguments: list[dict]):
        self.name = name
        self.description = description
        # Each argument: {name, description, required}
        self.arguments = arguments


class MCPResourceInfo:
    """Lightweight descriptor for an MCP resource."""

    def __init__(self, uri: str, name: str, description: str, mime_type: str):
        self.uri = uri  # stored as str via str(r.uri)
        self.name = name
        self.description = description
        self.mime_type = mime_type


class MCPClient:
    """Synchronous facade over an async MCP streamable HTTP session.

    Usage
    -----
    client = MCPClient()
    # client.tools      → list[MCPToolInfo]
    # client.prompts    → list[MCPPromptInfo]
    # client.resources  → list[MCPResourceInfo]
    # client.call_tool("list_segmentations", {})  → str
    # client.get_prompt("segment_deep_dive", {"segment_name": "...", "country": "..."})  → str
    # client.read_resource("resource://...")  → str
    # client.shutdown()
    """

    def __init__(self):
        self._tools: list[MCPToolInfo] = []
        self._prompts: list[MCPPromptInfo] = []
        self._resources: list[MCPResourceInfo] = []
        self._session: ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._initialized = threading.Event()
        self._init_error: Exception | None = None

        self._thread = threading.Thread(
            target=self._thread_main, name="mcp-session", daemon=True
        )
        self._thread.start()

        # Wait up to 60 s for the MCP server to connect and initialise
        if not self._initialized.wait(timeout=60):
            raise RuntimeError(
                "MCP server did not initialise within 60 s. "
                "Check network connectivity and server availability."
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
        async with streamable_http_client(REMOTE_MCP_URL) as (read, write, _):
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

                prompts_result = await session.list_prompts()
                self._prompts = [
                    MCPPromptInfo(
                        name=p.name,
                        description=p.description or "",
                        arguments=[
                            {
                                "name": a.name,
                                "description": a.description or "",
                                "required": a.required or False,
                            }
                            for a in (p.arguments or [])
                        ],
                    )
                    for p in prompts_result.prompts
                ]

                resources_result = await session.list_resources()
                self._resources = [
                    MCPResourceInfo(
                        uri=str(r.uri),
                        name=r.name,
                        description=r.description or "",
                        mime_type=r.mimeType or "",
                    )
                    for r in resources_result.resources
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

    @property
    def prompts(self) -> list[MCPPromptInfo]:
        return self._prompts

    @property
    def resources(self) -> list[MCPResourceInfo]:
        return self._resources

    def get_openai_tools(self) -> list[dict]:
        return [t.to_openai_function() for t in self._tools]

    def get_prompt(self, name: str, arguments: dict[str, str]) -> str:
        """Synchronously render an MCP prompt and return its text content."""
        if self._session is None or self._loop is None:
            raise RuntimeError("MCP client is not initialised.")

        async def _get():
            result = await self._session.get_prompt(name, arguments)  # type: ignore[union-attr]
            parts: list[str] = []
            for msg in result.messages:
                if hasattr(msg.content, "text"):
                    parts.append(msg.content.text)
            return "\n\n".join(parts)

        future = asyncio.run_coroutine_threadsafe(_get(), self._loop)
        try:
            return future.result(timeout=30)
        except Exception as exc:
            logger.error("Prompt %r failed: %s", name, exc)
            raise

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

    def read_resource(self, uri: str) -> str:
        """Synchronously read an MCP resource and return its text content."""
        if self._session is None or self._loop is None:
            raise RuntimeError("MCP client is not initialised.")

        async def _read():
            result = await self._session.read_resource(AnyUrl(uri))  # type: ignore[union-attr]
            parts: list[str] = []
            for content_item in result.contents:
                if hasattr(content_item, "text"):
                    parts.append(content_item.text)
            return "\n".join(parts) if parts else ""

        future = asyncio.run_coroutine_threadsafe(_read(), self._loop)
        try:
            return future.result(timeout=30)
        except Exception as exc:
            logger.error("Resource read %r failed: %s", uri, exc)
            return json.dumps({"error": str(exc)})

    def shutdown(self):
        """Signal the background thread to exit cleanly."""
        if self._stop_event and self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._thread.join(timeout=5)
