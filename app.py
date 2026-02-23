"""Pathways AI Assistant – Streamlit Chat UI

Connects a local Pathways MCP server (stdio subprocess) to OpenAI's
reasoning model so non-technical users can explore the Pathways health
segmentation platform through a conversational interface.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Bootstrap: load .env and Streamlit secrets
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent.resolve()
load_dotenv(_HERE / ".env")

# Support Streamlit Cloud secrets (they override the .env if present)
try:
    for _key in ("OPENAI_API_KEY", "PATHWAYS_API_TOKEN", "PATHWAYS_API_URL"):
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass  # No secrets.toml present — rely on .env instead

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pathways AI Assistant",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Pathways brand CSS  (Inter + Inter Tight, brand colours)
# Deliberately avoids span/svg so Streamlit's Material Icons are untouched.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Inter+Tight:wght@500;600;700&display=swap');

    body, p, li, label, input, textarea,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] div,
    [data-testid="stSidebarContent"] p,
    [data-testid="stSidebarContent"] label,
    [data-testid="stSelectbox"] div {
        font-family: 'Inter', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter Tight', sans-serif !important;
        color: #073F8C !important;
        letter-spacing: -0.02em;
    }

    a { color: #F28518 !important; }
    hr { border-color: #FFD9B2 !important; opacity: 1 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_PATH = _HERE / "system_prompt.md"

AVAILABLE_MODELS = {
    "gpt-5.2 — latest (default)": "gpt-5.2",
    "o4-mini — fast reasoning": "o4-mini",
    "o3-mini — previous reasoning": "o3-mini",
    "gpt-5 — standard": "gpt-5",
    "gpt-4o — standard": "gpt-4o",
}

TOOL_ICON = "🔧"
USER_ICON = "👤"
ASSISTANT_ICON = "🌍"

SUGGESTIONS = {
    "🌍 Which countries have data?": "Which countries have Pathways data available?",
    "📊 Most vulnerable segments": "Show me the most vulnerable population segments available in the Pathways data.",
    "👩 Segment profile (Senegal)": "Give me a detailed profile of the most vulnerable segment in Senegal.",
    "📍 Geographic distribution": "Where are the most vulnerable women geographically concentrated in Senegal?",
}


# ---------------------------------------------------------------------------
# Pure helper functions (defined before any Streamlit rendering)
# ---------------------------------------------------------------------------

def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are a helpful assistant for the Pathways health segmentation platform."


def make_conversation_id() -> str:
    return str(uuid.uuid4())[:8]


def get_or_create_conversation(conv_id: str) -> dict:
    if conv_id not in st.session_state.conversations:
        st.session_state.conversations[conv_id] = {
            "id": conv_id,
            "title": "New conversation",
            "created_at": datetime.now(),
            "display_messages": [],  # richer records for rendering
        }
    return st.session_state.conversations[conv_id]


def title_from_first_user_message(conv: dict) -> str:
    for msg in conv["display_messages"]:
        if msg["role"] == "user":
            text = msg["content"]
            return text[:60] + ("…" if len(text) > 60 else "")
    return "New conversation"


def render_tool_call(tc: dict):
    """Render a completed MCP tool call as a collapsible expander."""
    status = "error" if tc.get("is_error") else "complete"
    label = f"🔧 `{tc['name']}`"
    with st.expander(label, expanded=False):
        col_req, col_res = st.columns(2)
        with col_req:
            st.caption("Request")
            st.json(tc.get("arguments", {}))
        with col_res:
            st.caption("Response")
            result = tc.get("result", "")
            try:
                st.json(json.loads(result) if isinstance(result, str) else result)
            except (json.JSONDecodeError, TypeError):
                st.code(result, language=None)


def render_conversation(conv: dict):
    """Render all messages in a conversation."""
    for msg in conv["display_messages"]:
        if msg["role"] == "user":
            with st.chat_message("user", avatar=USER_ICON):
                st.markdown(msg["content"])
        elif msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=ASSISTANT_ICON):
                for tc in msg.get("tool_calls", []):
                    render_tool_call(tc)
                if msg.get("content"):
                    st.markdown(msg["content"])


def reconstruct_llm_messages(conv: dict, new_user_prompt: str) -> list[dict]:
    """Build the OpenAI messages array from display history + new user prompt.

    Each assistant display-message stores `_llm_sequence`: the exact list of
    OpenAI-format messages (assistant + tool results, potentially across several
    tool-call rounds) that were produced during that turn.  Replaying that
    sequence is the only way to get the tool_call_id pairing right when there
    were multiple rounds of tool use in a single turn.
    """
    messages: list[dict] = [{"role": "system", "content": load_system_prompt()}]
    for dm in conv["display_messages"]:
        if dm["role"] == "user":
            messages.append({"role": "user", "content": dm["content"]})
        elif dm["role"] == "assistant":
            if dm.get("_llm_sequence"):
                # Accurate replay: includes intermediate tool-calling rounds
                messages.extend(dm["_llm_sequence"])
            else:
                # Fallback for messages saved before this fix
                asst_msg: dict = {"role": "assistant", "content": dm.get("content") or ""}
                if dm.get("_raw_tool_calls"):
                    asst_msg["tool_calls"] = dm["_raw_tool_calls"]
                    asst_msg["content"] = dm.get("content") or None
                messages.append(asst_msg)
                for tc in dm.get("tool_calls", []):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["call_id"],
                        "content": tc["result"],
                    })
    messages.append({"role": "user", "content": new_user_prompt})
    return messages


def get_mcp_client():
    """Return the singleton MCPClient, creating it on first call."""
    if "mcp_client" not in st.session_state or st.session_state.mcp_client is None:
        from mcp_client import MCPClient

        token = os.environ.get("PATHWAYS_API_TOKEN", "")
        url = os.environ.get("PATHWAYS_API_URL", "")
        env = {}
        if token:
            env["PATHWAYS_API_TOKEN"] = token
        if url:
            env["PATHWAYS_API_URL"] = url

        with st.spinner("Starting Pathways MCP server…"):
            try:
                st.session_state.mcp_client = MCPClient(env=env)
            except Exception as exc:
                st.session_state.mcp_client = None
                st.error(f"Failed to start MCP server: {exc}")
                return None

    return st.session_state.mcp_client


# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
if "conversations" not in st.session_state:
    st.session_state.conversations = {}

if "current_conv_id" not in st.session_state:
    first_id = make_conversation_id()
    st.session_state.current_conv_id = first_id
    get_or_create_conversation(first_id)

if "mcp_client" not in st.session_state:
    st.session_state.mcp_client = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🌍 Pathways AI")
    st.caption("Health segmentation assistant powered by MCP + OpenAI")

    st.divider()

    # Model selection
    model_label = st.selectbox(
        "Model",
        list(AVAILABLE_MODELS.keys()),
        index=0,
        help="Reasoning models produce higher-quality analysis but may be slower.",
    )
    selected_model = AVAILABLE_MODELS[model_label]

    # Reasoning effort — only relevant for o-series models
    reasoning_effort = "medium"
    if selected_model.startswith("o"):
        reasoning_effort = st.select_slider(
            "Reasoning effort",
            options=["low", "medium", "high"],
            value="medium",
            help="Higher effort → better reasoning, slower response.",
        )

    st.divider()

    # New conversation
    if st.button("＋ New conversation", use_container_width=True, type="primary"):
        new_id = make_conversation_id()
        st.session_state.current_conv_id = new_id
        get_or_create_conversation(new_id)
        st.rerun()

    # Conversation list
    st.subheader("Conversations")
    conv_ids_sorted = sorted(
        st.session_state.conversations.keys(),
        key=lambda cid: st.session_state.conversations[cid]["created_at"],
        reverse=True,
    )
    for cid in conv_ids_sorted:
        conv = st.session_state.conversations[cid]
        display_title = title_from_first_user_message(conv)
        is_active = cid == st.session_state.current_conv_id

        col_btn, col_del = st.columns([8, 1])
        with col_btn:
            if st.button(
                display_title,
                key=f"conv_{cid}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.current_conv_id = cid
                st.rerun()
        with col_del:
            if st.button("✕", key=f"del_{cid}", help="Delete this conversation"):
                del st.session_state.conversations[cid]
                if st.session_state.current_conv_id == cid:
                    if st.session_state.conversations:
                        st.session_state.current_conv_id = next(
                            iter(st.session_state.conversations)
                        )
                    else:
                        new_id = make_conversation_id()
                        st.session_state.current_conv_id = new_id
                        get_or_create_conversation(new_id)
                st.rerun()

    st.divider()

    # MCP server status panel
    client = st.session_state.mcp_client
    if client is not None:
        tools = client.tools
        api_url = os.environ.get("PATHWAYS_API_URL", "").rstrip("/")
        st.success(f"✅ MCP connected — {len(tools)} tools")
        st.caption(f"Server: `{api_url}`")
        with st.expander("Available tools", expanded=False):
            for t in tools:
                desc_short = t.description[:100] + "…" if len(t.description) > 100 else t.description
                st.markdown(f"**`{t.name}`**  \n{desc_short}")

        prompts = getattr(client, "prompts", [])
        if prompts:
            st.markdown("**Prompts**")
            for p in prompts:
                with st.expander(f"💬 {p.name.replace('_', ' ').title()}", expanded=True):
                    if p.description:
                        st.caption(p.description)
                    with st.form(key=f"prompt_form_{p.name}"):
                        arg_vals: dict[str, str] = {}
                        for arg in p.arguments:
                            label = arg["name"].replace("_", " ").title()
                            arg_vals[arg["name"]] = st.text_input(
                                label,
                                placeholder=arg.get("description", ""),
                            )
                        if st.form_submit_button("Send prompt", use_container_width=True, type="primary"):
                            missing = [a["name"] for a in p.arguments if a.get("required") and not arg_vals.get(a["name"])]
                            if missing:
                                st.error(f"Required: {', '.join(missing)}")
                            else:
                                try:
                                    rendered = client.get_prompt(p.name, arg_vals)
                                    st.session_state["_pending_prompt"] = rendered
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Error: {exc}")
    else:
        st.warning("⚠️ MCP server not connected")
        st.caption("Responses will use the model's general knowledge only.")
        if st.button("Connect MCP server", use_container_width=True, type="primary"):
            get_mcp_client()
            st.rerun()

    st.divider()

    with st.expander("Configuration"):
        api_key_set = bool(os.environ.get("OPENAI_API_KEY"))
        token_set = bool(os.environ.get("PATHWAYS_API_TOKEN"))
        st.markdown(f"- OpenAI API key: {'✅' if api_key_set else '❌ missing'}")
        st.markdown(f"- Pathways token: {'✅' if token_set else '❌ missing'}")
        st.markdown(f"- Model: `{selected_model}`")
        st.markdown(f"- System prompt: `{SYSTEM_PROMPT_PATH.name}`")


# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
current_conv = get_or_create_conversation(st.session_state.current_conv_id)

st.header("Pathways AI Assistant", divider="orange")

# Show suggestion chips on empty conversations
if not current_conv["display_messages"]:
    st.markdown("Ask me anything about the Pathways health segmentation platform:")
    selected_chip = st.pills(
        "Suggestions",
        list(SUGGESTIONS.keys()),
        label_visibility="collapsed",
    )
    if selected_chip:
        prompt_from_chip = SUGGESTIONS[selected_chip]
        current_conv["display_messages"].append(
            {"role": "user", "content": prompt_from_chip}
        )
        # We'll fall through to the response generation below on the next rerun
        # but we need to trigger a rerun first so the message is rendered
        # Actually: just set a flag and let it flow through — but chips only trigger
        # a rerun when clicked. We'll handle it via st.rerun() here and then the
        # "pending prompt" will be picked up.
        st.session_state["_pending_prompt"] = prompt_from_chip
        st.rerun()

# Render all stored messages (historical)
render_conversation(current_conv)

# ---------------------------------------------------------------------------
# Handle a pending prompt (set by suggestion chips or new chat_input)
# ---------------------------------------------------------------------------

# Resolve the user prompt from either chat_input or a pending chip selection
prompt = st.chat_input("Ask about Pathways health data…")

# If a chip queued a prompt on the last rerun, pick it up
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

pending = st.session_state.pop("_pending_prompt", None)
if pending:
    st.session_state.pending_prompt = pending

active_prompt: str | None = prompt or st.session_state.pending_prompt
if active_prompt:
    st.session_state.pending_prompt = None  # consume it

if active_prompt:
    # Validate OpenAI key
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        st.error("OPENAI_API_KEY is not set. Add it to your .env file.")
        st.stop()

    # Use the MCP client only if already connected — never auto-start here.
    # If not connected the LLM responds from its own knowledge (no tools).
    mcp = st.session_state.mcp_client

    # Append the new user message to display history (if not already there via chip)
    last_display = current_conv["display_messages"]
    if not last_display or last_display[-1].get("content") != active_prompt or last_display[-1].get("role") != "user":
        current_conv["display_messages"].append({"role": "user", "content": active_prompt})

    # Render the user message
    with st.chat_message("user", avatar=USER_ICON):
        st.markdown(active_prompt)

    # Build OpenAI messages from full display history (excluding the message we just added,
    # since reconstruct_llm_messages appends it as the final user turn)
    conv_without_last = {
        **current_conv,
        "display_messages": current_conv["display_messages"][:-1],
    }
    llm_messages = reconstruct_llm_messages(conv_without_last, active_prompt)

    openai_tools = mcp.get_openai_tools() if mcp is not None else []
    openai_client = OpenAI(api_key=openai_key)

    # -----------------------------------------------------------------------
    # Streaming response + tool-call loop
    # -----------------------------------------------------------------------
    with st.chat_message("assistant", avatar=ASSISTANT_ICON):
        # tool_area is created FIRST so tool calls render above the text
        tool_area = st.container()
        text_placeholder = st.empty()

        collected_tool_calls: list[dict] = []
        # Exact sequence of OpenAI messages produced this turn (for history replay)
        turn_llm_sequence: list[dict] = []
        final_response_text = ""

        for _round in range(10):  # safety cap on tool-call rounds
            # Build call params
            call_params: dict = dict(
                model=selected_model,
                messages=llm_messages,
                stream=True,
            )
            if openai_tools:
                call_params["tools"] = openai_tools
            if selected_model.startswith("o"):
                call_params["reasoning_effort"] = reasoning_effort

            try:
                stream = openai_client.chat.completions.create(**call_params)
            except Exception as exc:
                st.error(f"OpenAI error: {exc}")
                break

            # ---- Stream one response ----
            accumulated_text = ""
            accumulated_tcs: dict[int, dict] = {}  # index → {id, name, arguments}

            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta

                # Stream text tokens
                if delta.content:
                    accumulated_text += delta.content
                    text_placeholder.markdown(accumulated_text + "▌")

                # Accumulate tool-call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in accumulated_tcs:
                            accumulated_tcs[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            accumulated_tcs[idx]["id"] = tc_delta.id
                        fn = tc_delta.function
                        if fn:
                            if fn.name:
                                accumulated_tcs[idx]["name"] += fn.name
                            if fn.arguments:
                                accumulated_tcs[idx]["arguments"] += fn.arguments

            # Remove streaming cursor from any partial text
            if accumulated_text:
                text_placeholder.markdown(accumulated_text)

            # ---- Execute tool calls if any ----
            if accumulated_tcs:
                # Build the assistant message for this round
                raw_tc_list = [
                    {
                        "id": accumulated_tcs[i]["id"],
                        "type": "function",
                        "function": {
                            "name": accumulated_tcs[i]["name"],
                            "arguments": accumulated_tcs[i]["arguments"],
                        },
                    }
                    for i in sorted(accumulated_tcs.keys())
                ]
                round_asst_msg = {
                    "role": "assistant",
                    "content": accumulated_text or None,
                    "tool_calls": raw_tc_list,
                }
                llm_messages.append(round_asst_msg)
                turn_llm_sequence.append(round_asst_msg)

                for i in sorted(accumulated_tcs.keys()):
                    tc = accumulated_tcs[i]
                    tool_name = tc["name"]
                    try:
                        tool_args = json.loads(tc["arguments"]) if tc["arguments"].strip() else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Show spinner while tool runs, then replace with result card
                    is_error = False
                    with tool_area:
                        with st.spinner(f"{TOOL_ICON} Running **`{tool_name}`**…"):
                            try:
                                result_text = mcp.call_tool(tool_name, tool_args)
                            except Exception as exc:
                                result_text = json.dumps({"error": str(exc)})
                                is_error = True
                        tc_record = {
                            "call_id": tc["id"],
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": result_text,
                            "is_error": is_error,
                        }
                        render_tool_call(tc_record)
                    collected_tool_calls.append(tc_record)

                    # Add tool result to LLM history (this round)
                    tool_result_msg = {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_text,
                    }
                    llm_messages.append(tool_result_msg)
                    turn_llm_sequence.append(tool_result_msg)

                # Continue to next round with tool results in context
                continue

            # ---- No tool calls → this is the final response ----
            final_response_text = accumulated_text
            # Record the final assistant message in the sequence too
            turn_llm_sequence.append({"role": "assistant", "content": final_response_text})
            break

        if final_response_text:
            text_placeholder.markdown(final_response_text)
        else:
            text_placeholder.empty()

    # Persist the completed assistant turn
    current_conv["display_messages"].append({
        "role": "assistant",
        "content": final_response_text,
        "tool_calls": collected_tool_calls,
        # Full LLM message sequence for accurate history reconstruction
        "_llm_sequence": turn_llm_sequence,
    })

    # Auto-set conversation title after the first exchange
    if len(current_conv["display_messages"]) == 2:
        current_conv["title"] = title_from_first_user_message(current_conv)
