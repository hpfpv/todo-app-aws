import { config } from './config';

type Sender = 'user' | 'bot';

let ws: WebSocket | null = null;

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

export function displayMessage(text: string, sender: Sender = 'user'): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);

    if (sender === 'bot') {
        messageElement.innerHTML = '<span class="bot-avatar-sm">✦</span>' + text;
    } else {
        messageElement.textContent = text;
    }

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
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