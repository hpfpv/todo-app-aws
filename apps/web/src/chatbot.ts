import { config } from './config';

type Sender = 'user' | 'bot';

interface PersistedMessage {
    text: string;
    sender: Sender;
}

const CHAT_HISTORY_KEY = 'chatHistory';
const CHAT_FRESH_KEY = 'chatFreshSession';
const UPLOAD_INTENT_RE = /upload|attach|add a file|share a file|provide the file|drag.*file|file.*url/i;

let ws: WebSocket | null = null;
let _intentionalClose = false;

let _streamingBubble: HTMLElement | null = null;
let _streamingText = '';

function setStatus(label: string, connected: boolean): void {
    const el = document.querySelector<HTMLElement>('.drawer-status');
    if (!el) return;
    el.textContent = `● ${label}`;
    el.classList.toggle('connected', connected);
}

function persistMessage(text: string, sender: Sender): void {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    const history: PersistedMessage[] = raw ? JSON.parse(raw) : [];
    history.push({ text, sender });
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history));
}

export function restoreChatHistory(): void {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    if (!raw) return;
    const history: PersistedMessage[] = JSON.parse(raw);
    history.forEach(({ text, sender }) => displayMessage(text, sender, false));
}

export function clearChatHistory(): void {
    localStorage.removeItem(CHAT_HISTORY_KEY);
    // Mark that next WS connection should start a fresh Bedrock session
    localStorage.setItem(CHAT_FRESH_KEY, '1');
}

function formatBotText(text: string): string {
    let s = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Inline markdown — bold and code. Applied AFTER escaping so the source
    // text can't introduce HTML; the tags we emit here are the only HTML
    // in the output.
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    s = s.replace(/\n/g, '<br>');
    return s;
}

export function openChatSession(): void {
    if (ws && ws.readyState === WebSocket.OPEN) return; // already connected

    const stored = localStorage.getItem('sessionTokens');
    if (!stored) {
        window.location.href = './index.html';
        return;
    }
    let tokens: { IdToken?: { jwtToken?: string } };
    try {
        tokens = JSON.parse(stored);
    } catch {
        window.location.href = './index.html';
        return;
    }
    const token: string = tokens?.IdToken?.jwtToken ?? '';
    if (!token) {
        window.location.href = './index.html';
        return;
    }

    // If this is a fresh login (after logout), request a new Bedrock session
    const fresh = localStorage.getItem(CHAT_FRESH_KEY) === '1';
    if (fresh) localStorage.removeItem(CHAT_FRESH_KEY);

    const url = `${config.chatbotWsEndpoint}?token=${encodeURIComponent(token)}${fresh ? '&fresh=1' : ''}`;
    setStatus('Connecting…', false);
    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log('[chatbot] WebSocket connected');
        setStatus('Online', true);
    };

    ws.onmessage = (event: MessageEvent) => {
        const frame = JSON.parse(event.data as string);
        if (frame.type === 'chunk') {
            appendChunk(frame.text as string);
        } else if (frame.type === 'done') {
            finalizeStream();
        } else if (frame.type === 'error') {
            removeTypingIndicator();
            replaceStreamWithError(frame.text as string);
        }
    };

    ws.onerror = () => {
        removeTypingIndicator();
        setStatus('Error', false);
        displayMessage('Connection error. Please refresh the page.', 'bot');
    };

    ws.onclose = () => {
        console.log('[chatbot] WebSocket closed');
        ws = null;
        if (_intentionalClose) {
            _intentionalClose = false;
            setStatus('Offline', false);
            return;
        }
        // Unexpected close (server timeout) — auto-reconnect if drawer still open
        const drawer = document.getElementById('chatDrawer');
        if (drawer?.classList.contains('open')) {
            setStatus('Reconnecting…', false);
            setTimeout(() => openChatSession(), 1500);
        } else {
            setStatus('Offline', false);
        }
    };
}

export function closeChatSession(): void {
    _intentionalClose = true;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    ws = null;
}

export function displayMessage(text: string, sender: Sender = 'user', persist = true): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);

    if (sender === 'bot') {
        messageElement.innerHTML = '<span class="bot-avatar-sm">✦</span>' + formatBotText(text);
        if (persist) _maybeAppendUploadButton(messageElement);
    } else {
        messageElement.textContent = text;
    }

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (persist) persistMessage(text, sender);
}

export function displayTypingIndicator(): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    let typingIndicator = document.getElementById('typingIndicator');
    if (!typingIndicator) {
        typingIndicator = document.createElement('div');
        typingIndicator.classList.add('message', 'typing');
        typingIndicator.id = 'typingIndicator';
        typingIndicator.textContent = '...';
        chatMessages.appendChild(typingIndicator);
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

export function removeTypingIndicator(): void {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) typingIndicator.remove();
}

export function sendMessage(): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        displayMessage('Not connected. Please open the chat panel again.', 'bot');
        return;
    }

    const userInput = document.getElementById('userInput') as HTMLInputElement;
    const message = userInput.value.trim();
    if (!message) return;

    userInput.value = '';
    displayMessage(message, 'user');
    displayTypingIndicator();

    ws.send(JSON.stringify({ human: message }));
}

function appendChunk(text: string): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    _streamingText += text;

    if (!_streamingBubble) {
        removeTypingIndicator();
        const bubble = document.createElement('div');
        bubble.classList.add('message', 'bot');
        chatMessages.appendChild(bubble);
        _streamingBubble = bubble;
    }

    _streamingBubble.innerHTML =
        '<span class="bot-avatar-sm">✦</span>' + formatBotText(_streamingText);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function finalizeStream(): void {
    if (!_streamingBubble) return;
    persistMessage(_streamingText, 'bot');
    _maybeAppendUploadButton(_streamingBubble);
    _streamingBubble = null;
    _streamingText = '';
}

function replaceStreamWithError(text: string): void {
    if (_streamingBubble) {
        _streamingBubble.remove();
        _streamingBubble = null;
        _streamingText = '';
    }
    displayMessage(text, 'bot', true);
}

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