# Chatbot File Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paperclip button to the chat input row and keyword-triggered inline upload buttons so users can pick files from within the chatbot drawer.

**Architecture:** A single hidden `<input type="file" id="chatFileInput">` is shared by all triggers. A new `initChatFileInput()` function wires up the paperclip button and the file input's `change` handler. A shared `_handleFileUpload()` helper (private to `chatbot.ts`) deduplicates the upload-and-send logic currently inlined in the drop zone. After every bot message is rendered, a keyword regex check optionally appends an inline "📎 Upload file" button to the bubble.

**Tech Stack:** TypeScript, Vite, AWS SDK v3 S3 (`@aws-sdk/client-s3`), WebSocket, vanilla DOM

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `apps/web/home.html` | Modify | Add `#chatAttachBtn` + `#chatFileInput` to chat drawer |
| `apps/web/css/style.css` | Modify | Add `.chat-attach-btn` and `.chat-upload-btn` styles |
| `apps/web/src/chatbot.ts` | Modify | Extract `_handleFileUpload()`, add `initChatFileInput()`, add keyword scanner in `displayMessage()` |
| `apps/web/src/pages/home.ts` | Modify | Import + call `initChatFileInput()` in `openDrawer()` |

---

## Task 1: Add HTML structure

**Files:**
- Modify: `apps/web/home.html:61-64`

- [ ] **Step 1: Add the paperclip button and hidden file input**

  Open `apps/web/home.html`. Replace lines 61-64 (the `chat-input-row` div and its closing tag):

  ```html
          <div class="chat-input-row">
              <button id="chatAttachBtn" class="chat-attach-btn" aria-label="Attach file" type="button">📎</button>
              <input type="text" id="userInput" placeholder="Type a message…" class="chat-pill-input">
              <button id="sendMessageButton" class="chat-send-btn">➤</button>
          </div>
          <input type="file" id="chatFileInput" style="display:none" accept="*/*">
  ```

  The hidden file input goes **after** the `chat-input-row` div, still inside `#chatDrawer`.

- [ ] **Step 2: Verify the markup compiles**

  Run:
  ```bash
  cd apps/web && npm run build 2>&1 | tail -5
  ```
  Expected: build succeeds with no errors (TypeScript does not parse HTML, so this just confirms the build pipeline still works).

- [ ] **Step 3: Commit**

  ```bash
  git add apps/web/home.html
  git commit -m "feat(chat): add paperclip button and hidden file input to drawer"
  ```

---

## Task 2: Add CSS styles

**Files:**
- Modify: `apps/web/css/style.css` (after `.chat-send-btn` block, around line 375)

- [ ] **Step 1: Add button styles after the `.chat-send-btn` block**

  In `apps/web/css/style.css`, after the closing `}` of `.chat-send-btn` (line 375), insert:

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

  .chat-upload-btn {
      display: block;
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

- [ ] **Step 2: Verify build**

  ```bash
  cd apps/web && npm run build 2>&1 | tail -5
  ```
  Expected: build succeeds.

- [ ] **Step 3: Commit**

  ```bash
  git add apps/web/css/style.css
  git commit -m "feat(chat): add styles for attach button and inline upload button"
  ```

---

## Task 3: Refactor drop zone + add upload logic in chatbot.ts

**Files:**
- Modify: `apps/web/src/chatbot.ts`

The drop zone currently has the upload-and-send logic inlined. Extract it into a shared private helper so the new file input can reuse it without duplication.

- [ ] **Step 1: Add `_handleFileUpload` private helper**

  In `apps/web/src/chatbot.ts`, add this function directly above `export function initChatDropZone()` (before line 180):

  ```typescript
  async function _handleFileUpload(file: File): Promise<void> {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
          displayMessage('Not connected. Please open the chat panel again.', 'bot', false);
          return;
      }

      displayMessage(`Uploading ${file.name}…`, 'bot', false);
      displayTypingIndicator();

      try {
          const { uploadToS3 } = await import('./s3upload');
          const { config: appConfig } = await import('./config');
          const todoID = localStorage.getItem('todoID') ?? '';
          const key = await uploadToS3(file, todoID || 'unassigned');
          const fileUrl = `https://${appConfig.cdnDomain}/${key}`;

          removeTypingIndicator();

          const msg = todoID
              ? `I just uploaded "${file.name}". Its URL is: ${fileUrl}. Please attach it to the currently open todo.`
              : `I just uploaded "${file.name}". Its URL is: ${fileUrl}. Please ask me which todo to attach it to.`;

          displayMessage(msg, 'user');
          displayTypingIndicator();
          ws.send(JSON.stringify({ human: msg }));
      } catch (err) {
          removeTypingIndicator();
          displayMessage('File upload failed. Please try again.', 'bot', false);
          console.error('[chatbot] file upload error:', err);
      }
  }
  ```

- [ ] **Step 2: Refactor `initChatDropZone` to use `_handleFileUpload`**

  Replace the `drop` handler inside `initChatDropZone` (lines 197-229). The full updated `initChatDropZone` should read:

  ```typescript
  export function initChatDropZone(): void {
      const drawer = document.getElementById('chatDrawer');
      if (!drawer) return;

      if (drawer.dataset.dropzoneInit) return;
      drawer.dataset.dropzoneInit = '1';

      drawer.addEventListener('dragover', (e: DragEvent) => {
          e.preventDefault();
          drawer.classList.add('drag-over');
      });

      drawer.addEventListener('dragleave', () => {
          drawer.classList.remove('drag-over');
      });

      drawer.addEventListener('drop', async (e: DragEvent) => {
          e.preventDefault();
          drawer.classList.remove('drag-over');
          const file = e.dataTransfer?.files?.[0];
          if (!file) return;
          await _handleFileUpload(file);
      });
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles**

  ```bash
  cd apps/web && npm run build 2>&1 | tail -5
  ```
  Expected: build succeeds, no TypeScript errors.

- [ ] **Step 4: Commit**

  ```bash
  git add apps/web/src/chatbot.ts
  git commit -m "refactor(chat): extract _handleFileUpload helper from drop zone"
  ```

---

## Task 4: Add keyword scanner and `initChatFileInput` to chatbot.ts

**Files:**
- Modify: `apps/web/src/chatbot.ts`

- [ ] **Step 1: Add the upload-intent regex constant**

  At the top of `apps/web/src/chatbot.ts`, after the existing constants (after line 18, `SESSION_TTL_SECONDS`), add:

  ```typescript
  const UPLOAD_INTENT_RE = /upload|attach|add a file|share a file|provide the file|drag.*file|file.*url/i;
  ```

- [ ] **Step 2: Add `_maybeAppendUploadButton` private helper**

  Add this function directly above `_handleFileUpload` (which you added in Task 3):

  ```typescript
  function _maybeAppendUploadButton(el: HTMLElement): void {
      const text = el.textContent ?? '';
      if (!UPLOAD_INTENT_RE.test(text)) return;
      const btn = document.createElement('button');
      btn.className = 'chat-upload-btn';
      btn.type = 'button';
      btn.textContent = '📎 Upload file';
      btn.addEventListener('click', () => {
          const fileInput = document.getElementById('chatFileInput') as HTMLInputElement | null;
          fileInput?.click();
      });
      el.appendChild(btn);
  }
  ```

- [ ] **Step 3: Call `_maybeAppendUploadButton` inside `displayMessage` for bot messages**

  In `displayMessage`, find the block that handles `sender === 'bot'` (around line 131-133):

  ```typescript
  if (sender === 'bot') {
      messageElement.innerHTML = '<span class="bot-avatar-sm">✦</span>' + formatBotText(text);
  }
  ```

  Replace it with:

  ```typescript
  if (sender === 'bot') {
      messageElement.innerHTML = '<span class="bot-avatar-sm">✦</span>' + formatBotText(text);
      if (persist) _maybeAppendUploadButton(messageElement);
  }
  ```

  The `persist` guard ensures the upload button only appears on live messages — not when history is restored from `localStorage` (where `displayMessage` is called with `persist = false`).

- [ ] **Step 4: Add `initChatFileInput` export**

  Add this exported function at the end of `apps/web/src/chatbot.ts` (after `initChatDropZone`):

  ```typescript
  export function initChatFileInput(): void {
      const fileInput = document.getElementById('chatFileInput') as HTMLInputElement | null;
      const attachBtn = document.getElementById('chatAttachBtn') as HTMLButtonElement | null;
      if (!fileInput || !attachBtn) return;

      if (fileInput.dataset.chatInit) return;
      fileInput.dataset.chatInit = '1';

      attachBtn.addEventListener('click', () => fileInput.click());

      fileInput.addEventListener('change', async () => {
          const file = fileInput.files?.[0];
          fileInput.value = '';
          if (!file) return;
          await _handleFileUpload(file);
      });
  }
  ```

- [ ] **Step 5: Verify TypeScript compiles**

  ```bash
  cd apps/web && npm run build 2>&1 | tail -5
  ```
  Expected: build succeeds, no TypeScript errors.

- [ ] **Step 6: Commit**

  ```bash
  git add apps/web/src/chatbot.ts
  git commit -m "feat(chat): add keyword scanner and initChatFileInput for click-to-upload"
  ```

---

## Task 5: Wire up in home.ts

**Files:**
- Modify: `apps/web/src/pages/home.ts:1-3`

- [ ] **Step 1: Import `initChatFileInput`**

  In `apps/web/src/pages/home.ts`, update the import from `../chatbot` (line 2):

  ```typescript
  import { sendMessage, openChatSession, closeChatSession, restoreChatHistory, clearChatHistory, initChatDropZone, initChatFileInput } from '../chatbot';
  ```

- [ ] **Step 2: Call `initChatFileInput()` in `openDrawer`**

  In `home.ts`, find the `openDrawer` function (around line 26). Add the call after `initChatDropZone()`:

  ```typescript
  function openDrawer(): void {
      if (!chatDrawer || !chatFab) return;
      chatDrawer.classList.add('open');
      chatFab.style.display = 'none';
      openChatSession();
      initChatDropZone();
      initChatFileInput();
      (document.getElementById('userInput') as HTMLInputElement)?.focus();
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles cleanly**

  ```bash
  cd apps/web && npm run build 2>&1 | tail -5
  ```
  Expected: build succeeds with no errors.

- [ ] **Step 4: Commit**

  ```bash
  git add apps/web/src/pages/home.ts
  git commit -m "feat(chat): wire up initChatFileInput in openDrawer"
  ```

---

## Task 6: Manual verification

- [ ] **Step 1: Run local dev server**

  ```bash
  cd apps/web && npm run dev
  ```
  Open `http://localhost:5173/home.html` (requires being logged in — use `.env.local` credentials).

- [ ] **Step 2: Verify paperclip button appears**

  Open the chat drawer. Confirm a 📎 button appears to the left of the text input. Hovering it should turn it teal.

- [ ] **Step 3: Verify click-to-upload via paperclip**

  Click 📎. A native file picker should open. Select any file. Confirm:
  - An "Uploading filename…" bot bubble appears
  - A user bubble with the file URL appears
  - The agent responds (may ask which todo if none is open, or attach directly if a todo modal was open)

- [ ] **Step 4: Verify inline upload button appears on agent prompts**

  Type: `I want to add a file to a todo` and send. When the agent responds with language like "please upload" or "attach", confirm a `📎 Upload file` pill button appears at the bottom of that bot bubble.

- [ ] **Step 5: Verify drop zone still works**

  Drag a file onto the chat drawer. Confirm it still uploads and sends as before (regression check).

- [ ] **Step 6: Push branch**

  ```bash
  git push origin feat/cloudfront-oac-nova-agent-refresh
  ```
