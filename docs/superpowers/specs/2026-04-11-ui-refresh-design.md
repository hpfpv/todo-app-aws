# UI Refresh — Chatbot Drawer & Todo Cards

Date: 2026-04-11
Status: Approved

## Scope

Two areas: chatbot UI (drawer + FAB) and todo list UI (navbar, cards, stats bar).
CSS and markup changes only — no backend, no API, no routing changes.

Files touched:

- `css/style.css` — chatbot and todo sections rewritten
- `src/chatbot.ts` — bot avatar markup + path fix
- `src/ui.ts` — `renderTodos()` card markup
- `home.html` — navbar, toolbar, stats bar, chat drawer HTML

---

## Color System

Shared across chatbot and todo UI. Single consistent palette.

| Token | Value | Usage |
|---|---|---|
| `--teal` | `#0d9488` | Primary accent, active borders, send button, links |
| `--teal-light` | `#f0fdfa` | Button hover bg, card tint |
| `--teal-border` | `#99f6e4` | Teal button borders |
| `--green` | `#22c55e` | Completed status |
| `--amber` | `#f59e0b` | Overdue status |
| `--surface` | `#f0f2f5` | Page background |
| `--card` | `#ffffff` | Card / drawer background |
| `--text-primary` | `#111827` | Main text |
| `--text-secondary` | `#64748b` | Secondary / meta text |
| `--border` | `#e2e8f0` | Borders, dividers |

---

## 1. Navbar

Replace the centered logo block + separate toolbar with a single compact navbar.

**Structure:**

```
[ logo.png (height 36px) ]   [ search pill ]  [ + New todo ]  [ Sign out ]
```

- White background, `border-bottom: 1px solid #e5e7eb`, `padding: 12px 20px`
- Logo: existing `img/logo.png`, `height: 36px`, `width: auto` — no text brand mark
- Search: pill input (`background: #f1f5f9`, `border-radius: 20px`) + search icon
- **New todo**: `background: #0d9488`, white text, `border-radius: 8px`
- **Sign out**: transparent, `border: 1px solid #e2e8f0`, `border-radius: 8px`

---

## 2. Stats Bar

Thin bar below navbar showing live counts.

```
[ 10 Total ]  [ 6 In Progress ]  [ 4 Done ]
```

- White pill cards, `border-radius: 8px`, `border: 1px solid #e2e8f0`
- Count: `font-size: 16px`, `font-weight: 700`
  - Total: `color: #0d9488`
  - In Progress: `color: #f59e0b`
  - Done: `color: #22c55e`
- Label: `9px`, uppercase, `color: #94a3b8`
- Counts derived from the `todos` array in `renderTodos()` — no extra API call

---

## 3. Todo Cards

Replaces `renderTodos()` in `ui.ts`. Grid layout unchanged (`col-md-4`).

**Card anatomy:**

```
┌─ 3px left border (status color) ──────────────────┐
│  Title (bold)                   [status badge]    │
│  Description (2 lines max, truncated)             │
│  📅 Due date                                      │
│  [ Open ]  (full-width teal button)               │
└────────────────────────────────────────────────────┘
```

**Status rules:**

| State | Left border | Badge text | Badge bg | Title style |
|---|---|---|---|---|
| In progress | `#0d9488` | `● In progress` | `#f0fdf4 / #16a34a` | Normal |
| Completed | `#22c55e` | `✓ Done` | `#f0fdf4 / #22c55e` | Strikethrough, muted |
| Overdue | `#f59e0b` | `⚠ Overdue` | `#fffbeb / #d97706` | Normal |

Overdue = `dateDue < today && !completed`. Computed client-side in `renderTodos()`.

**Open button:** `background: #f0fdfa`, `color: #0d9488`, `border: 1px solid #99f6e4`. Muted on completed cards.

---

## 4. Chatbot — Bottom Drawer

Replaces fixed floating panel. Slides up from bottom, full viewport width.

**Trigger:** FAB click → drawer opens. ✕ button or second FAB click → drawer closes.

**Drawer structure:**

```
┌── drag handle (centered bar) ─────────────────────┐
│  [✦ teal avatar]  Assistant        ● Online   [✕] │
│  ────────────────────────────────────────────────  │
│  message area (#fafafa bg, scrollable)            │
│  ────────────────────────────────────────────────  │
│  [ pill input ........................... ]  [➤]  │
└────────────────────────────────────────────────────┘
```

- Height: `45vh`
- `border-radius: 16px 16px 0 0`
- `box-shadow: 0 -4px 20px rgba(0,0,0,0.12)`
- Animation: `transform: translateY(100%)` → `translateY(0)`, `transition: 300ms ease-out`
- `position: fixed; bottom: 0; left: 0; right: 0; z-index: 1000`

**Header:**
- Teal circle avatar (32px) with `✦` symbol — replaces SVG bot icon
- "Assistant" bold label, "● Online" in `#22c55e` below
- ✕ close button right-aligned

**Messages:**
- Bot: left-aligned, white bubble `border: 1px solid #e2e8f0`, `border-radius: 4px 14px 14px 14px`, teal ✦ avatar left
- User: right-aligned, `background: #0d9488`, white text, `border-radius: 14px 4px 14px 14px`
- Background: `#fafafa`

**Input:**
- Pill input: `border-radius: 24px`, `background: #f8fafc`
- Send button: teal circle (36px), `➤` icon

**Bot icon path fix:**
`src="public/img/bot-icon.svg"` → `src="/img/bot-icon.svg"` in `chatbot.ts`

---

## 5. FAB

- Size: 48px circle
- `background: linear-gradient(135deg, #0d9488, #0891b2)`
- `✦` symbol, white, `font-size: 18px`
- `box-shadow: 0 4px 14px rgba(13,148,136,0.4)`
- Hidden (`display: none`) when drawer is open; shown when closed

---

## Out of Scope

- Login, register, confirm pages — not touched
- Modal design (description modal, new todo modal) — not touched in this pass
- Backend, API, auth — no changes
- Mobile breakpoints beyond what Bootstrap provides — deferred
