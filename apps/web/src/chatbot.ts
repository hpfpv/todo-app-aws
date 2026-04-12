import { config } from './config';

type Sender = 'user' | 'bot';

interface PersistedMessage {
    text: string;
    sender: Sender;
}

const CHAT_HISTORY_KEY = 'chatHistory';
const CHAT_FRESH_KEY = 'chatFreshSession';

let ws: WebSocket | null = null;

function setStatus(label: string, online: boolean): void {
    const el = document.querySelector<HTMLElement>('.drawer-status');
    if (!el) return;
    el.textContent = `● ${label}`;
    el.style.color = online ? '' : 'var(--clr-muted, #999)';
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
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
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
        const data = JSON.parse(event.data as string);
        removeTypingIndicator();
        displayMessage(data.response, 'bot');
    };

    ws.onerror = () => {
        removeTypingIndicator();
        setStatus('Error', false);
        displayMessage('Connection error. Please refresh the page.', 'bot');
    };

    ws.onclose = () => {
        console.log('[chatbot] WebSocket closed');
        setStatus('Offline', false);
        ws = null;
    };
}

export function closeChatSession(): void {
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

export function initChatDropZone(): void {
    const drawer = document.getElementById('chatDrawer');
    if (!drawer) return;

    // Prevent re-registering listeners
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
        if (!file || !ws || ws.readyState !== WebSocket.OPEN) return;

        displayMessage(`Uploading ${file.name}…`, 'bot', false);
        displayTypingIndicator();

        try {
            const { uploadToS3 } = await import('./s3upload');
            const { config: appConfig } = await import('./config');
            const todoID = localStorage.getItem('todoID') ?? '';
            const key = await uploadToS3(file, todoID || 'unassigned');
            const fileUrl = `https://${appConfig.cdnDomain}/${key}`;

            removeTypingIndicator();
            displayMessage(
                `File "${file.name}" uploaded. I'll ask the AI to attach it to a todo.`,
                'bot',
                false,
            );

            const msg = `I just uploaded a file named "${file.name}". Its URL is: ${fileUrl}. Please attach it to the appropriate todo, or ask me which todo to attach it to.`;
            displayMessage(msg, 'user');
            displayTypingIndicator();
            ws.send(JSON.stringify({ human: msg }));
        } catch (err) {
            removeTypingIndicator();
            displayMessage('File upload failed. Please try again.', 'bot', false);
            console.error('[chatbot] drop upload error:', err);
        }
    });
}