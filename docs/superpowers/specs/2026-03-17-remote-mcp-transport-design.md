# Remote MCP Transport — Design Spec

**Date:** 2026-03-17
**Status:** Approved (v4 — final)

## Goal

Replace the local stdio MCP subprocess with a connection to the remote FastMCP server at `https://pathways.fastmcp.app/mcp`. The Streamlit UI must continue to support tools, prompts, and resources without changes to `app.py` logic beyond cosmetic/cleanup updates.

## Background

Currently `mcp_client.py` spawns `run_server.py` as a child process via the MCP stdio transport, running the `pathways_mcp` Python package locally. The refactor switches to the MCP streamable HTTP transport, which the remote FastMCP server already exposes at `/mcp`.

The `pathways_mcp` package is not in `requirements.txt` — it was only ever used by the local subprocess. No dependency manifest changes are needed.

## Approach

Option A: minimal transport swap. Keep the background-thread / sync-facade architecture unchanged. Replace only the transport initialisation inside `_run_session`.

## MCP SDK version note

The project uses `mcp==1.26.0`. In this version, `mcp.client.streamable_http` exports two names:
- `streamable_http_client` (line 601) — current, non-deprecated ✅
- `streamablehttp_client` (line 686) — deprecated alias; do **not** use

All code in this spec uses `streamable_http_client`.

---

## Changes

### `mcp_client.py`

**Imports to remove:**
- `StdioServerParameters`, `stdio_client` from `mcp.client.stdio`
- `os`
- `sys`
- `Path` from `pathlib`

**Imports to add:**
- `streamable_http_client` from `mcp.client.streamable_http`
- `AnyUrl` from `pydantic` (for `read_resource` URI coercion)

**Constants to remove:**
- `_STREAMLIT_UI_DIR`

**New constant:**
```python
REMOTE_MCP_URL = "https://pathways.fastmcp.app/mcp"
```

**`MCPClient.__init__`:**
- Remove `env` parameter and `self._env` assignment entirely
- Add `self._resources: list[MCPResourceInfo] = []` to initialisation block
- Update class docstring example to `MCPClient()` (no args)

**`_run_session` transport swap:**

Remove entirely:
```python
merged_env = {**os.environ, **self._env}
params = StdioServerParameters(
    command=sys.executable,
    args=[str(_STREAMLIT_UI_DIR / "run_server.py")],
    env=merged_env,
)
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
```

Replace with:
```python
async with streamable_http_client(REMOTE_MCP_URL) as (read, write, _):
    async with ClientSession(read, write) as session:
```

`streamable_http_client` yields a 3-tuple `(read_stream, write_stream, get_session_id_callback)`. The third element is discarded with `_`.

**New descriptor class `MCPResourceInfo`** (add alongside `MCPToolInfo` and `MCPPromptInfo`):
```python
class MCPResourceInfo:
    def __init__(self, uri: str, name: str, description: str, mime_type: str):
        self.uri = uri        # stored as str via str(r.uri)
        self.name = name
        self.description = description
        self.mime_type = mime_type
```

`uri` is stored as `str` (via `str(r.uri)`) so that callers work with plain strings. The `AnyUrl` coercion in `read_resource` is therefore always necessary.

**Resources listing in `_run_session`:** after `list_prompts()`, add:
```python
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
```

**New `resources` property** (consistent with existing `tools` and `prompts` — no separate method):
```python
@property
def resources(self) -> list[MCPResourceInfo]:
    return self._resources
```

**New `read_resource(uri: str) -> str` method** (same thread-dispatch pattern as `call_tool`):
- Coerce: `AnyUrl(uri)` before passing to `session.read_resource()`
- Collect text parts from `result.contents` (items with `.text` attribute)
- Blob-only content → return `""`; multi-item text → `"\n".join(parts)`
- Error → log and return `json.dumps({"error": str(exc)})`

**Timeout:** The existing 60-second `_initialized.wait` timeout in `__init__` is appropriate for an HTTP connection and is preserved unchanged.

---

### `app.py`

**Module docstring (~line 2–5):** update from "Connects a local Pathways MCP server (stdio subprocess)…" to "Connects to the remote Pathways MCP server at https://pathways.fastmcp.app/mcp…"

**Imports:** add `REMOTE_MCP_URL` to the `from mcp_client import MCPClient` line:
```python
from mcp_client import MCPClient, REMOTE_MCP_URL
```

**`os` import:** retain — still needed for `os.environ` access in secrets bootstrap, config expander, and prompt handling.

**Secrets bootstrap (~lines 26–30):** simplify to remove the now-dead `PATHWAYS_API_TOKEN` and `PATHWAYS_API_URL`:
```python
try:
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass
```

**`get_mcp_client()` (~lines 199–220) — remove dead code:**
- Remove `token = os.environ.get("PATHWAYS_API_TOKEN", "")`
- Remove `url = os.environ.get("PATHWAYS_API_URL", "")`
- Remove `env = {}` and the two `if` blocks that populate it
- Change `MCPClient(env=env)` → `MCPClient()`
- Change spinner text: `"Starting Pathways MCP server…"` → `"Connecting to Pathways MCP server…"`

**Sidebar MCP status panel (~lines 317–319) — fix stale caption:**

Remove:
```python
api_url = os.environ.get("PATHWAYS_API_URL", "").rstrip("/")
st.success(f"✅ MCP connected — {len(tools)} tools")
st.caption(f"Server: `{api_url}`")
```

Replace with:
```python
st.success(f"✅ MCP connected — {len(tools)} tools")
st.caption(f"Server: `{REMOTE_MCP_URL}`")
```

**Configuration expander (~lines 361–364) — remove dead token check:**

Remove both lines:
```python
token_set = bool(os.environ.get("PATHWAYS_API_TOKEN"))
st.markdown(f"- Pathways token: {'✅' if token_set else '❌ missing'}")
```

---

### `run_server.py`

**Delete.** No longer needed — the server runs remotely.

### `pathways_mcp/`

No changes. Server-side package, unaffected by the client refactor.

---

## Data Flow

```
Streamlit app.py
    └── get_mcp_client()  →  MCPClient (singleton in session_state)
            └── background thread (own asyncio loop)
                    └── streamable_http_client("https://pathways.fastmcp.app/mcp")
                            └── (read, write, _)
                                    └── ClientSession(read, write)
                                            ├── list_tools()       → self._tools
                                            ├── list_prompts()     → self._prompts
                                            ├── list_resources()   → self._resources
                                            ├── call_tool(name, args)
                                            ├── get_prompt(name, args)
                                            └── read_resource(AnyUrl(uri))
```

## Error Handling

No new error paths. Connection failures (network unreachable, timeout, non-2xx) surface via the existing `_init_error` / `threading.Event` mechanism → `st.error(...)` in `app.py`.

`read_resource` errors are caught and returned as `json.dumps({"error": ...})` — same contract as `call_tool`.

## Out of Scope

- Authentication (server is open access; `PATHWAYS_API_TOKEN` was for the local subprocess only)
- Surfacing resources in the `app.py` sidebar UI (follow-on)
