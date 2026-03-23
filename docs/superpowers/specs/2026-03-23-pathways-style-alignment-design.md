# Pathways Style Alignment — Design Spec

**Date:** 2026-03-23
**Branch:** align-withpathways-style
**Status:** Approved

---

## Overview

Reskin the Streamlit chat UI to visually align with the withpathways.org design system. The goal is **aligned but adapted**: adopt withpathways.org's blue color family for primary elements while retaining a warm orange accent for interactive highlights. All changes stay within Streamlit's CSS injection model — no new dependencies or custom components.

---

## Design Tokens

These CSS custom properties mirror withpathways.org's design system and are declared at the top of the injected CSS block:

| Token | Value | Usage |
|---|---|---|
| `--pw-blue` | `#0B6BCB` | Primary buttons, links, active states |
| `--pw-blue-dark` | `#185EA5` | Hover states |
| `--pw-blue-darker` | `#12467B` | Headings (h1–h6), logo fill, section titles |
| `--pw-blue-tint` | `#E3F0FF` | Active conversation background in sidebar |
| `--pw-accent` | `#F28518` | Warm accent: header divider gradient, chips |
| `--pw-accent-soft` | `#FFF0E0` | Soft accent backgrounds |
| `--pw-bg` | `#FBFCFE` | Page background (subtle blue-white tint) |
| `--pw-surface` | `#F0F4F8` | Card/panel backgrounds |
| `--pw-border` | `#DDE7EE` | Dividers, borders, hr elements |
| `--pw-text` | `#171A1C` | Body text |
| `--pw-text-muted` | `#636B74` | Captions, secondary labels |

**What changes vs current:**
- `#073F8C` (dark navy headings) → `#12467B` (withpathways.org blue-darker)
- `#0B6BCB` replaces generic Streamlit blue for primary interactive elements
- `#FFD9B2` (warm orange borders) → `#DDE7EE` (cool gray borders)
- Orange accent `#F28518` is **kept** but scoped: header divider gradient + suggestion chips only

---

## Typography

No changes to font families — Inter (body) and Inter Tight (headings) already match withpathways.org.

- Heading `letter-spacing: -0.02em` — keep
- Heading `color` updated to `--pw-blue-darker` (`#12467B`)
- Link `color` updated to `--pw-blue` (`#0B6BCB`)

---

## Logo

- **File:** `assets/logo.svg` (extracted from withpathways.org, already committed)
- **Usage:** Read at startup via `Path("assets/logo.svg").read_text()`, embed as inline SVG in the sidebar via `st.markdown(svg_html, unsafe_allow_html=True)`, replacing the `st.title("🌍 Pathways AI")` call (which must be deleted)
- **Color:** Every `<path>` in the SVG has a hardcoded `fill="black"` attribute. Override in the injected CSS with:
  ```css
  [data-testid="stSidebarContent"] .sidebar-logo svg path {
      fill: #12467B !important;
  }
  ```
  Alternatively, strip `fill="black"` from the SVG source before writing to `assets/logo.svg` and use a plain CSS rule without `!important`.
- **Size:** Rendered at `130×28px` (scaled from native `165×36px`) via `width="130" height="28"` on the `<svg>` element
- **Caption** "Health segmentation assistant powered by MCP + OpenAI" rendered as `st.caption()` below the logo markdown block

---

## Sidebar

- Background: white (`#FFFFFF`) with right border `--pw-border`; selector: `[data-testid="stSidebar"] > div`
- Primary buttons (both "＋ New conversation" and the active conversation entry): selector `[data-testid="stSidebarContent"] [data-testid="baseButton-primary"]` — `background: var(--pw-blue)`, white text, `border-radius: 6px`. **Both buttons intentionally share the same blue primary style** — they are visually distinct by position (top vs. list). No further scoping needed.
- Secondary/inactive conversation buttons: selector `[data-testid="stSidebarContent"] [data-testid="baseButton-secondary"]` — transparent background, `color: var(--pw-text-muted)`, hover `background: var(--pw-surface)`. This also covers the ✕ delete buttons (which are unstyled secondaries), which receive the same treatment — acceptable.
- `st.divider()` calls render as `<hr>` — covered globally by `hr { border-color: var(--pw-border) }`
- Section titles rendered by `st.subheader()`: selector `[data-testid="stSidebarContent"] h3` — `color: var(--pw-blue-darker)`, Inter Tight

---

## Main Chat Area

- Page background: `--pw-bg` (`#FBFCFE`); selector: `.stApp, [data-testid="stAppViewContainer"]`
- Header: replace `st.header("Pathways AI Assistant", divider="orange")` with:
  ```python
  st.markdown("""
  <h1 class="pw-page-title">Pathways AI Assistant</h1>
  <div class="pw-title-divider"></div>
  """, unsafe_allow_html=True)
  ```
  CSS:
  ```css
  .pw-page-title { font-family: 'Inter Tight', sans-serif; font-size: 1.75rem;
                   font-weight: 700; color: #12467B; letter-spacing: -0.02em; margin-bottom: 0.25rem; }
  .pw-title-divider { height: 2px; border-radius: 2px;
                      background: linear-gradient(90deg, var(--pw-blue), var(--pw-accent)); margin-bottom: 1rem; }
  ```
- Suggestion pills: `st.pills` renders with `data-testid="stPillsInput"` in Streamlit ≥1.40. Selector: `[data-testid="stPillsInput"] button` — `border: 1px solid var(--pw-border)`, `color: var(--pw-blue-dark)`, hover `background: var(--pw-blue-tint)`. If pills don't respond (due to Streamlit version rendering differences), fall back to `.stPills button`.
- Tool-call expanders: selector `[data-testid="stExpander"]` — `background: var(--pw-surface)`, `border: 1px solid var(--pw-border)`, `border-radius: 6px`
- `hr` dividers: `hr { border-color: var(--pw-border) !important; opacity: 1 !important; }` (was `#FFD9B2`)

---

## Implementation Approach

**Single CSS block with custom properties** (Approach B, chosen by user):

1. **Rewrite the `st.markdown()` CSS block** (lines 47–73 of `app.py`):
   - Add `:root { --pw-blue: #0B6BCB; ... }` token declarations at the top
   - Replace hardcoded color values with `var(--pw-*)` references
   - Add new selectors for `.stApp`, `[data-testid="stSidebar"]`, `[data-testid="baseButton-primary"]`, `[data-testid="baseButton-secondary"]`, `[data-testid="stExpander"]`, pill buttons, and the custom `.pw-page-title` / `.pw-title-divider` classes
2. **Logo injection** — add immediately after line 24 (`load_dotenv(_HERE / ".env")`), before the `st.secrets` block:
   ```python
   _LOGO_SVG = (_HERE / "assets" / "logo.svg").read_text(encoding="utf-8")
   ```
   In the sidebar block, replace `st.title("🌍 Pathways AI")` with:
   ```python
   st.markdown(f'<div class="sidebar-logo">{_LOGO_SVG}</div>', unsafe_allow_html=True)
   st.caption("Health segmentation assistant powered by MCP + OpenAI")
   ```
3. **Header replacement** — replace `st.header("Pathways AI Assistant", divider="orange")` with the `st.markdown()` HTML block described in the Main Chat Area section above.

No new files except `assets/logo.svg` (already present).

---

## Scope

| Area | Change |
|---|---|
| Colors & Typography | ✅ Full token system, updated heading/link colors |
| Sidebar | ✅ Logo, button colors, active state, dividers |
| Chat area | ✅ Header, divider, pills, tool expanders, background |
| Branding / Logo | ✅ Real SVG replacing emoji |

---

## Out of Scope

- Dark mode
- Streamlit component replacements
- Layout changes (sidebar width, column structure)
- Functional changes to chat, MCP, or model logic
- Browser tab icon (`page_icon="🌍"` in `st.set_page_config`) — Streamlit only supports emoji or image URLs for the favicon; the SVG logo cannot be used here without converting to PNG. Leave as-is.
