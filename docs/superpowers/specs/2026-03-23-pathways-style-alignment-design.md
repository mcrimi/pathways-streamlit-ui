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
- **Usage:** Read at startup, embed as inline SVG in the sidebar title area, replacing the `🌍 Pathways AI` text
- **Color:** SVG `fill` overridden via CSS to `--pw-blue-darker` (`#12467B`)
- **Size:** Rendered at `130×28px` (scaled from native `165×36px`)
- **Caption** "Health segmentation assistant powered by MCP + OpenAI" remains below

---

## Sidebar

- Background: white (`#FFFFFF`) with right border `--pw-border`
- Primary button ("＋ New conversation"): `background: --pw-blue`, white text
- Secondary/inactive conversation buttons: styled with `--pw-surface` hover
- Active conversation: `background: #E3F0FF`, `color: --pw-blue-dark`
- Dividers: `border-color: --pw-border`
- Section titles (e.g. "Conversations"): `color: --pw-blue-darker`, Inter Tight

---

## Main Chat Area

- Page background: `--pw-bg` (`#FBFCFE`)
- Header `st.header("Pathways AI Assistant", divider="orange")` — replace with custom HTML heading + a `linear-gradient(90deg, --pw-blue, --pw-accent)` divider bar
- Suggestion pills: border `--pw-border`, text `--pw-blue-dark`, hover background `#E3F0FF`
- Tool-call expanders: background `--pw-surface`, border `--pw-border`
- `hr` dividers: `border-color: --pw-border` (was `#FFD9B2`)

---

## Implementation Approach

**Single CSS block with custom properties** (Approach B, chosen by user):

1. Rewrite the existing `st.markdown()` CSS block in `app.py` to:
   - Declare all `--pw-*` custom properties in `:root`
   - Use those variables throughout all selectors
2. Load `assets/logo.svg` at startup using `Path.read_text()` and inject it inline as HTML in the sidebar title
3. Replace `st.header(..., divider="orange")` with `st.markdown()` HTML heading + custom divider

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
