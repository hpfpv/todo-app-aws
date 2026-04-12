# UI Refresh — Chatbot Drawer & Todo Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing navbar, chat panel, and todo cards with a redesigned compact navbar, bottom-drawer chatbot, and status-aware todo cards.

**Architecture:** CSS/markup-only refresh across four files. Color tokens defined once in `:root`, consumed everywhere. Stats bar counts computed client-side inside `renderTodos()`. Chat drawer is CSS-driven (`transform: translateY`) toggled by adding/removing `.open` class.

**Tech Stack:** TypeScript, Vite, Bootstrap 4 (existing), CSS custom properties

---

## File Structure

| File | Action | What changes |
|---|---|---|
| `apps/web/home.html` | Modify | Replace logo block + toolbar + old chat HTML with navbar, stats bar, drawer, FAB |
| `apps/web/css/style.css` | Modify | Add `:root` tokens; add navbar, stats bar, card, drawer, FAB styles; remove old chat block + global `button` reset |
| `apps/web/src/ui.ts` | Modify | Rewrite `renderTodos()` with status cards; add `updateStatsBar()` |
| `apps/web/src/chatbot.ts` | Modify | `displayMessage()` — replace `<img>` icon with `✦` span; remove unused path |
| `apps/web/src/pages/home.ts` | Modify | Replace `.chat-tab` / `.chat-container` toggle with `#chatFab`, `#chatDrawer`, `#chatCloseBtn` |

---

## Task 1: CSS — Color Tokens and Body Reset

**Files:**
- Modify: `apps/web/css/style.css` (prepend to file)

- [ ] **Step 1: Add color tokens at the very top of style.css**

Open `apps/web/css/style.css`. Prepend these lines before the existing `#logo` rule:

```css
/* ── Color tokens ───────────────────────────────── */
:root {
  --teal:           #0d9488;
  --teal-light:     #f0fdfa;
  --teal-border:    #99f6e4;
  --green:          #22c55e;
  --amber:          #f59e0b;
  --surface:        #f0f2f5;
  --card:           #ffffff;
  --text-primary:   #111827;
  --text-secondary: #64748b;
  --border:         #e2e8f0;
}

body {
  background: var(--surface);
  margin: 0;
}

```

- [ ] **Step 2: Remove the global button reset (it conflicts with new button styles)**

Find and delete lines 235–238 in `apps/web/css/style.css` — the bare `button { ... }` rule:

```css
  button {
    padding: 10px;
    border: none;
    margin: 5px;
  }
```

Delete only that block. Leave all other rules untouched.

- [ ] **Step 3: Build to verify no CSS parse errors**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/css/style.css
git commit -m "chore(web): add CSS color tokens and remove conflicting button reset"
```

---

## Task 2: home.html — Navbar + Stats Bar HTML

**Files:**
- Modify: `apps/web/home.html` (lines 15–51)

- [ ] **Step 1: Replace old logo block + toolbar with navbar + stats bar**

In `apps/web/home.html`, replace everything from `<!-- Logo -->` through the closing `<br><br>` on line 51 (i.e. lines 15–51) with:

```html
    <!-- Navbar -->
    <nav class="site-navbar">
        <a href="#" class="navbar-logo">
            <img src="img/logo.png" alt="Logo" style="height:36px;width:auto;">
        </a>
        <div class="navbar-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <input type="text" id="searchTodosFilter" placeholder="Search todos…">
        </div>
        <div class="navbar-actions">
            <button type="button" id="addTodoButton" class="btn-primary-nav" data-toggle="modal" data-target="#newTodoModal">+ New todo</button>
            <button type="button" id="signOutButton" class="btn-outline-nav">Sign out</button>
        </div>
    </nav>

    <!-- Stats bar -->
    <div class="stats-bar">
        <div class="stat-pill">
            <span class="stat-count" id="statTotal" style="color:var(--teal)">0</span>
            <span class="stat-label">TOTAL</span>
        </div>
        <div class="stat-pill">
            <span class="stat-count" id="statInProgress" style="color:var(--amber)">0</span>
            <span class="stat-label">IN PROGRESS</span>
        </div>
        <div class="stat-pill">
            <span class="stat-count" id="statDone" style="color:var(--green)">0</span>
            <span class="stat-label">DONE</span>
        </div>
    </div>
```

The HTML immediately after (`<!-- Chatbot -->`) is replaced in Task 3.

- [ ] **Step 2: Build to confirm no TypeScript errors**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/home.html
git commit -m "feat(web): replace logo+toolbar with compact navbar and stats bar"
```

---

## Task 3: home.html — Chatbot Drawer + FAB HTML

**Files:**
- Modify: `apps/web/home.html`

- [ ] **Step 1: Replace old chatbot HTML with drawer + FAB**

In `apps/web/home.html`, find and replace the old chatbot block (lines 23–33 in the original, now positioned right after the stats bar):

```html
    <!-- Chatbot -->
    <div class="chat-tab">
        <img src="img/bot-icon.gif" alt="Chat with us!" style="width: 100%; height: 100%;">
    </div>
    <div class="chat-container">
        <div class="messages" id="chatMessages"></div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Type a message...">
            <button id="sendMessageButton">Send</button>
        </div>
    </div>
```

Replace it with:

```html
    <!-- Chat FAB -->
    <button id="chatFab" class="chat-fab" aria-label="Open assistant">✦</button>

    <!-- Chat Drawer -->
    <div id="chatDrawer" class="chat-drawer">
        <div class="drawer-handle"></div>
        <div class="drawer-header">
            <div class="drawer-avatar">✦</div>
            <div class="drawer-identity">
                <strong>Assistant</strong>
                <span class="drawer-status">● Online</span>
            </div>
            <button id="chatCloseBtn" class="drawer-close" aria-label="Close">✕</button>
        </div>
        <div class="chat-messages" id="chatMessages"></div>
        <div class="chat-input-row">
            <input type="text" id="userInput" placeholder="Type a message…" class="chat-pill-input">
            <button id="sendMessageButton" class="chat-send-btn">➤</button>
        </div>
    </div>
```

- [ ] **Step 2: Build to confirm**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/home.html
git commit -m "feat(web): replace floating chat panel with bottom drawer and FAB"
```

---

## Task 4: home.ts — Update Chatbot Event Handlers

**Files:**
- Modify: `apps/web/src/pages/home.ts`

The existing code queries `.chat-tab` and `.chat-container` which no longer exist. Replace with `#chatFab`, `#chatDrawer`, `#chatCloseBtn`.

- [ ] **Step 1: Replace the chatbot toggle block in home.ts**

Find this block in `apps/web/src/pages/home.ts` (lines 15–29):

```typescript
    // Chatbot toggle
    const chatTab = document.querySelector('.chat-tab');
    const chatContainer = document.querySelector('.chat-container') as HTMLElement | null;
    chatTab?.addEventListener('click', () => {
        if (!chatContainer) return;
        const isOpen = chatContainer.style.display === 'flex';
        if (isOpen) {
            chatContainer.style.display = 'none';
            closeChatSession();
        } else {
            chatContainer.style.display = 'flex';
            openChatSession();
            (document.getElementById('userInput') as HTMLInputElement)?.focus();
        }
    });
```

Replace it with:

```typescript
    // Chatbot — FAB and drawer toggle
    const chatFab = document.getElementById('chatFab') as HTMLElement | null;
    const chatDrawer = document.getElementById('chatDrawer') as HTMLElement | null;
    const chatCloseBtn = document.getElementById('chatCloseBtn') as HTMLElement | null;

    function openDrawer(): void {
        if (!chatDrawer || !chatFab) return;
        chatDrawer.classList.add('open');
        chatFab.style.display = 'none';
        openChatSession();
        (document.getElementById('userInput') as HTMLInputElement)?.focus();
    }

    function closeDrawer(): void {
        if (!chatDrawer || !chatFab) return;
        chatDrawer.classList.remove('open');
        chatFab.style.display = 'flex';
        closeChatSession();
    }

    chatFab?.addEventListener('click', openDrawer);
    chatCloseBtn?.addEventListener('click', closeDrawer);
```

- [ ] **Step 2: Build to confirm TypeScript compiles**

```bash
cd apps/web && npm run build 2>&1 | tail -10
```

Expected: `✓ built in` with no errors. If you see `'chatTab' is declared but its value is never read`, that confirms the old code is gone.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/pages/home.ts
git commit -m "feat(web): wire FAB open and close button for chat drawer"
```

---

## Task 5: chatbot.ts — Avatar Markup Fix

**Files:**
- Modify: `apps/web/src/chatbot.ts` (line 65)

- [ ] **Step 1: Replace the bot icon in displayMessage()**

Find this block in `apps/web/src/chatbot.ts` (lines 62–68):

```typescript
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);

    const botIcon = '<img src="public/img/bot-icon.svg" alt="Bot" style="width: 20px; height: 20px;"> ';
    const icon = sender === 'user' ? '&#128100; ' : botIcon;
    messageElement.innerHTML = icon + text;
```

Replace it with:

```typescript
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);

    if (sender === 'bot') {
        messageElement.innerHTML = '<span class="bot-avatar-sm">✦</span>' + text;
    } else {
        messageElement.textContent = text;
    }
```

- [ ] **Step 2: Build to confirm**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/chatbot.ts
git commit -m "fix(web): replace bot SVG icon with teal ✦ span avatar in chat messages"
```

---

## Task 6: ui.ts — Redesigned Todo Cards + Stats Bar

**Files:**
- Modify: `apps/web/src/ui.ts` (lines 50–71)

- [ ] **Step 1: Rewrite renderTodos() and add updateStatsBar()**

Find and replace the `renderTodos` function (lines 50–71) in `apps/web/src/ui.ts`:

```typescript
  export function renderTodos(todos: Todo[]): void {
      const list = getElement('todosList');
      if (!list) return;
      list.innerHTML = todos.map(todo => `
          <div class="col-md-4 border border-info" style="margin-bottom: 1rem;">
              <br>
              <p align="center">
                  <strong>${todo.title}</strong><br>
                  ${todo.description}<br>
                  <b>Due Date:</b> ${todo.dateDue}<br>
                  <button type="button"
                      class="btn btn-sm"
                      data-toggle="modal"
                      data-target="#descriptionModal"
                      data-todoid="${todo.todoID}">
                      Details
                  </button>
              </p>
              <br>
          </div>
      `).join('');
  }
```

Replace with:

```typescript
  export function renderTodos(todos: Todo[]): void {
      const list = getElement('todosList');
      if (!list) return;

      const today = new Date().toISOString().split('T')[0];

      list.innerHTML = todos.map(todo => {
          const isOverdue = !todo.completed && !!todo.dateDue && todo.dateDue < today;
          const statusClass = todo.completed ? 'status-done' : isOverdue ? 'status-overdue' : 'status-inprogress';
          const badgeHtml = todo.completed
              ? '<span class="todo-badge badge-done">✓ Done</span>'
              : isOverdue
                  ? '<span class="todo-badge badge-overdue">⚠ Overdue</span>'
                  : '<span class="todo-badge badge-inprogress">● In progress</span>';
          const titleClass = todo.completed ? 'todo-title-done' : '';

          return `
<div class="col-md-4 mb-3">
  <div class="todo-card ${statusClass}">
    <div class="todo-card-top">
      <span class="todo-title ${titleClass}">${todo.title}</span>
      ${badgeHtml}
    </div>
    <p class="todo-desc">${todo.description}</p>
    <p class="todo-due">📅 ${todo.dateDue || '—'}</p>
    <button type="button"
        class="todo-open-btn${todo.completed ? ' todo-open-btn-muted' : ''}"
        data-toggle="modal"
        data-target="#descriptionModal"
        data-todoid="${todo.todoID}">
      Open
    </button>
  </div>
</div>`;
      }).join('');

      updateStatsBar(todos);
  }

  export function updateStatsBar(todos: Todo[]): void {
      const done = todos.filter(t => t.completed).length;
      const inProgress = todos.length - done;
      const setCount = (id: string, n: number) => {
          const el = document.getElementById(id);
          if (el) el.textContent = String(n);
      };
      setCount('statTotal', todos.length);
      setCount('statInProgress', inProgress);
      setCount('statDone', done);
  }
```

- [ ] **Step 2: Build to confirm TypeScript compiles cleanly**

```bash
cd apps/web && npm run build 2>&1 | tail -10
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/ui.ts
git commit -m "feat(web): redesign todo cards with status borders, badges, and live stats"
```

---

## Task 7: CSS — Navbar and Stats Bar Styles

**Files:**
- Modify: `apps/web/css/style.css` (append)

- [ ] **Step 1: Append navbar and stats bar CSS to style.css**

Add to the end of `apps/web/css/style.css`:

```css
/* ── Navbar ─────────────────────────────────────── */
.site-navbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    background: var(--card);
    border-bottom: 1px solid #e5e7eb;
    position: sticky;
    top: 0;
    z-index: 100;
}

.navbar-logo img {
    display: block;
}

.navbar-search {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f1f5f9;
    border-radius: 20px;
    padding: 6px 14px;
    flex: 1;
    max-width: 320px;
}

.navbar-search input {
    border: none;
    background: transparent;
    outline: none;
    font-size: 14px;
    width: 100%;
    color: var(--text-primary);
}

.navbar-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
}

.btn-primary-nav {
    background: var(--teal);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 14px;
    cursor: pointer;
}

.btn-outline-nav {
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 14px;
    cursor: pointer;
}

/* ── Stats bar ──────────────────────────────────── */
.stats-bar {
    display: flex;
    gap: 10px;
    padding: 10px 20px;
    background: var(--surface);
}

.stat-pill {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 80px;
}

.stat-count {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.2;
}

.stat-label {
    font-size: 9px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
```

- [ ] **Step 2: Build to confirm**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/css/style.css
git commit -m "feat(web): add navbar and stats bar CSS"
```

---

## Task 8: CSS — Todo Card Styles

**Files:**
- Modify: `apps/web/css/style.css` (append)

- [ ] **Step 1: Append todo card CSS to style.css**

Add to the end of `apps/web/css/style.css`:

```css
/* ── Todo cards ─────────────────────────────────── */
.todo-card {
    background: var(--card);
    border-radius: 8px;
    border: 1px solid var(--border);
    border-left-width: 3px;
    border-left-style: solid;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.todo-card.status-inprogress { border-left-color: var(--teal); }
.todo-card.status-done       { border-left-color: var(--green); }
.todo-card.status-overdue    { border-left-color: var(--amber); }

.todo-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
}

.todo-title {
    font-weight: 700;
    font-size: 15px;
    color: var(--text-primary);
}

.todo-title-done {
    text-decoration: line-through;
    color: var(--text-secondary);
}

.todo-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 12px;
    white-space: nowrap;
    font-weight: 500;
    flex-shrink: 0;
}

.badge-inprogress { background: #f0fdf4; color: #16a34a; }
.badge-done       { background: #f0fdf4; color: var(--green); }
.badge-overdue    { background: #fffbeb; color: #d97706; }

.todo-desc {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
}

.todo-due {
    font-size: 12px;
    color: var(--text-secondary);
    display: block;
    margin: 0;
}

.todo-open-btn {
    width: 100%;
    background: var(--teal-light);
    color: var(--teal);
    border: 1px solid var(--teal-border);
    border-radius: 6px;
    padding: 6px 0;
    font-size: 13px;
    cursor: pointer;
}

.todo-open-btn-muted {
    opacity: 0.5;
}
```

- [ ] **Step 2: Build to confirm**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/css/style.css
git commit -m "feat(web): add todo card CSS with status-color left borders and badges"
```

---

## Task 9: CSS — Chatbot Drawer, FAB, and Message Styles

**Files:**
- Modify: `apps/web/css/style.css` — remove old chat block, append new drawer styles

- [ ] **Step 1: Remove old chatbot CSS block from style.css**

Find and delete the old chatbot styles in `apps/web/css/style.css` — the block spanning from `.chat-tab {` through the end of the file (lines 153–234 in the original):

```css
.chat-tab { ... }
#chatIcon { ... }
.chat-container { ... }
.messages { ... }
.message { ... }
.message img { ... }
.message.user { ... }
.message.bot { ... }
.chat-input { ... }
.chat-input input[type="text"] { ... }
```

Delete all of those rules.

- [ ] **Step 2: Append new chatbot drawer CSS to style.css**

Add to the end of `apps/web/css/style.css`:

```css
/* ── Chat FAB ───────────────────────────────────── */
.chat-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #0d9488, #0891b2);
    color: #fff;
    font-size: 18px;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(13, 148, 136, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
    padding: 0;
}

/* ── Chat Drawer ────────────────────────────────── */
.chat-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 45vh;
    background: var(--card);
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.12);
    z-index: 1000;
    display: flex;
    flex-direction: column;
    transform: translateY(100%);
    transition: transform 300ms ease-out;
}

.chat-drawer.open {
    transform: translateY(0);
}

.drawer-handle {
    width: 36px;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    margin: 10px auto 0;
    flex-shrink: 0;
}

.drawer-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.drawer-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--teal);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}

.drawer-identity {
    display: flex;
    flex-direction: column;
    flex: 1;
}

.drawer-identity strong {
    font-size: 14px;
    color: var(--text-primary);
}

.drawer-status {
    font-size: 11px;
    color: var(--green);
}

.drawer-close {
    background: none;
    border: none;
    font-size: 16px;
    cursor: pointer;
    color: var(--text-secondary);
    padding: 4px;
    line-height: 1;
}

/* ── Chat Messages ──────────────────────────────── */
.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    background: #fafafa;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.message {
    max-width: 80%;
    padding: 8px 12px;
    font-size: 14px;
    line-height: 1.4;
    border-radius: 8px;
}

.message.bot {
    align-self: flex-start;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 4px 14px 14px 14px;
    color: var(--text-primary);
    display: flex;
    align-items: flex-start;
    gap: 8px;
}

.bot-avatar-sm {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--teal);
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    flex-shrink: 0;
    margin-top: 1px;
}

.message.user {
    align-self: flex-end;
    background: var(--teal);
    color: #fff;
    border-radius: 14px 4px 14px 14px;
}

.message.typing {
    align-self: flex-start;
    color: var(--text-secondary);
    font-style: italic;
    background: none;
    border: none;
    padding: 4px 8px;
}

/* ── Chat Input ─────────────────────────────────── */
.chat-input-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
}

.chat-pill-input {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 8px 16px;
    background: #f8fafc;
    font-size: 14px;
    outline: none;
    color: var(--text-primary);
}

.chat-send-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--teal);
    color: #fff;
    border: none;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    flex-shrink: 0;
}
```

- [ ] **Step 3: Build to confirm**

```bash
cd apps/web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` with no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/css/style.css
git commit -m "feat(web): add chatbot drawer, FAB, and message styles"
```

---

## Task 10: Final Build Verification

**Files:** None — verification only.

- [ ] **Step 1: Clean build**

```bash
cd apps/web && npm run build 2>&1
```

Expected output: `✓ built in Xs` — no TypeScript errors, no Vite warnings about missing exports.

- [ ] **Step 2: Spot-check exports from ui.ts**

The following must still be exported from `apps/web/src/ui.ts` (required by `home.ts`):
- `renderTodos` ✓ (rewritten in Task 6)
- `markCompleted` ✓ (unchanged)
- `markNotCompleted` ✓ (unchanged)
- `showAddFilesForm` ✓ (unchanged)
- `hideAddFilesForm` ✓ (unchanged)
- `addFileName` ✓ (unchanged)

Confirm with:

```bash
grep "^  export function" apps/web/src/ui.ts
```

Expected: all six functions listed above.

- [ ] **Step 3: Start dev server and visually inspect**

```bash
cd apps/web && npm run dev
```

Open `http://localhost:5173/home.html` in a browser and verify:

1. **Navbar** — logo, search pill, "New todo" teal button, "Sign out" outline button visible in one row
2. **Stats bar** — three pills (Total, In Progress, Done) with correct colors
3. **FAB** — teal gradient circle with ✦ in bottom-right
4. **FAB click** — drawer slides up from bottom; FAB disappears
5. **✕ button** — drawer slides down; FAB reappears
6. **Todo cards** (after sign-in) — 3px colored left border, status badge, description clamped to 2 lines, "Open" teal button
7. **Stats counts** — update after todos load
8. **Chat send** — message appears in drawer with ✦ bot avatar for bot responses

- [ ] **Step 4: Final commit if any tweaks were made during inspection**

```bash
git add -p
git commit -m "fix(web): ui refresh visual tweaks from inspection"
```

---

## Spec Coverage Check

| Spec Section | Covered by Task |
|---|---|
| Color system — all tokens | Task 1 |
| Navbar — logo, search, buttons | Tasks 2, 7 |
| Stats bar — counts, colors | Tasks 2, 6, 7 |
| Todo cards — status borders, badges, truncation, open button | Tasks 6, 8 |
| Overdue detection (`dateDue < today && !completed`) | Task 6 |
| Chatbot drawer — slide-up, 45vh, border-radius, shadow | Tasks 3, 9 |
| Drawer header — avatar, Assistant label, Online, ✕ | Tasks 3, 9 |
| Messages — bot left / user right bubbles | Tasks 5, 9 |
| Input pill + send button | Tasks 3, 9 |
| FAB — gradient, ✦, shadow, hidden when open | Tasks 3, 9 |
| Bot icon path fix | Task 5 |
| Login/register/confirm/modals — not touched | ✓ out of scope |
