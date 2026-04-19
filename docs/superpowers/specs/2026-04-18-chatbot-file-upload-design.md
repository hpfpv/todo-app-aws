# Design: Chatbot File Upload

- **Date:** 2026-04-18
- **Status:** Approved

---

## Context

The chatbot drawer supports drag-and-drop file upload onto the drawer surface, but has
no click-to-upload affordance. When a user types "add a file to this todo", the agent
responds with text instructions but there is no way to actually pick a file from within
the chat UI. This design adds two complementary triggers for file upload inside the chat.

---

## Goals

- Always-visible paperclip button in the chat input row
- Agent responses containing upload-intent language automatically get an inline
  "Upload file" button appended to the message bubble
- Selecting a file through either trigger runs the same upload flow as the existing
  drop zone and sends the result to the agent via WebSocket

## Non-goals

- Backend / WebSocket protocol changes
- Replacing or removing the existing drag-and-drop drop zone
- Multi-file upload in a single interaction

---

## Approach

A single hidden `<input type="file">` lives in the DOM. Both the paperclip button and
any inline upload button call `.click()` on it. The `change` handler executes the upload
and sends the file URL to the agent. Keyword detection runs in `chatbot.ts` after every
bot message is rendered.

---

## UI Changes

### `apps/web/home.html`

Add to `.chat-input-row`, before the text input:

```html
<button id="chatAttachBtn" class="chat-attach-btn" aria-label="Attach file" type="button">📎</button>
```

Add after `.chat-input-row` (hidden, outside the row):

```html
<input type="file" id="chatFileInput" style="display:none" accept="*/*">
```

Result:

```
[ 📎 attach ] [ text input ] [ ➤ send ]
```

### `apps/web/css/style.css`

**Paperclip button** — same size as send button, neutral colour, teal on hover:

```css
.chat-attach-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #f0f0f0;
    color: var(--text-secondary);
    border: none;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 150ms;
}
.chat-attach-btn:hover {
    background: var(--teal);
    color: #fff;
}
```

**Inline upload button** — small pill appended to bot message bubbles:

```css
.chat-upload-btn {
    display: inline-block;
    margin-top: 8px;
    padding: 4px 12px;
    border-radius: 12px;
    background: var(--teal);
    color: #fff;
    font-size: 12px;
    border: none;
    cursor: pointer;
}
```

---

## Keyword Detection

After every bot message is rendered, `chatbot.ts` scans the text against a
case-insensitive regex. If matched, a `<button class="chat-upload-btn">` is appended
to that message bubble.

Trigger pattern:

```
/upload|attach|add a file|share a file|provide the file|drag.*file|file.*url/i
```

The button is injected once per message and is **not** persisted to `localStorage`
(will not re-appear on history restore — the paperclip is always available as fallback).

---

## Upload Flow

Triggered by either the paperclip button or an inline upload button:

1. Open the hidden `<input type="file">` via `.click()`
2. On `change`, read the selected `File`
3. Read `localStorage.getItem('todoID')` (currently open todo, may be empty)
4. Call `uploadToS3(file, todoID || 'unassigned')` — existing function, unchanged
5. Build CDN URL: `` `https://${config.cdnDomain}/${key}` ``
6. Display user bubble:
   - If `todoID` set: `I just uploaded "filename". Please attach it to the currently open todo.`
   - If no `todoID`: `I just uploaded "filename". Its URL is: <url>. Please ask me which todo to attach it to.`
7. Send the bubble text as the WebSocket message
8. Agent calls `addTodoFile` with the todo and file URL

This is the same pattern as the existing drop zone handler — the file input is a
click-triggered equivalent of drag-and-drop.

---

## Files Changed

| File | Change |
|------|--------|
| `apps/web/home.html` | Add `#chatAttachBtn` button and `#chatFileInput` hidden input |
| `apps/web/css/style.css` | Add `.chat-attach-btn` and `.chat-upload-btn` styles |
| `apps/web/src/chatbot.ts` | Add `initChatFileInput()`, keyword scanner in `displayMessage()`, wire `#chatAttachBtn` click in `home.ts` |

No backend changes required.

---

## Error Handling

- If upload fails, display bot bubble: `"File upload failed. Please try again."` (same as drop zone)
- If WebSocket is not open when file is selected, display: `"Not connected. Please open the chat panel again."` and abort
- Reset the file input value after each selection so the same file can be re-selected if needed
