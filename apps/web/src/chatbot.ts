import { config } from './config';

type Sender = 'user' | 'bot';

interface PersistedMessage {
    text: string;
    sender: Sender;
}

const CHAT_HISTORY_KEY = 'chatHistory';

let ws: WebSocket | null = null;

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

    ws = new WebSocket(`${config.chatbotWsEndpoint}?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
        console.log('[chatbot] WebSocket connected');
    };

    ws.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data as string);
        removeTypingIndicator();
        displayMessage(data.response, 'bot');
    };

    ws.onerror = () => {
        removeTypingIndicator();
        displayMessage('Connection error. Please refresh the page.', 'bot');
    };

    ws.onclose = () => {
        console.log('[chatbot] WebSocket closed');
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