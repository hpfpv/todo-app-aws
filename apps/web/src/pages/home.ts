import { getTodos, getTodo, addTodo, completeTodo, deleteTodo, addTodoNotes } from '../api';
import { logOut } from '../auth';
import { sendMessage, openChatSession, closeChatSession } from '../chatbot';
import { renderTodos, markCompleted, showAddFilesForm, hideAddFilesForm, addFileName } from '../ui';
import { Todo } from '../types';

document.addEventListener('DOMContentLoaded', () => {

    // Load todos on page load
    getTodos(renderTodos);

    // Sign out button
    document.getElementById('signOutButton')?.addEventListener('click', logOut);

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

    // Chatbot send on Enter
    document.getElementById('userInput')?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });

    // New todo form
    document.getElementById('newTodoForm')?.addEventListener('submit', (e: Event) => {
        e.preventDefault();
        const title = (document.getElementById('newTodoModalTitle') as HTMLInputElement).value;
        const dateDue = (document.getElementById('newTodoModalDateDue') as HTMLInputElement).value;
        const description = (document.getElementById('newTodoModalDescription') as HTMLTextAreaElement).value;
        addTodo(dateDue, title, description);
    });

    // Search todos
    document.getElementById('searchTodosButton')?.addEventListener('click', () => {
        // getSearchedTodos(filter, renderTodos); // wire up when ready
    });

    // Show all todos
    document.getElementById('showAllTodosButton')?.addEventListener('click', () => {
        (document.getElementById('searchTodosFilter') as HTMLInputElement).value = '';
        getTodos(renderTodos);
    });

    // Description modal — load todo details when opened
    document.getElementById('descriptionModal')?.addEventListener('show.bs.modal', (e: Event) => {
        const button = (e as any).relatedTarget as HTMLElement;
        const todoID = button?.dataset?.todoid;
        if (!todoID) return;
        localStorage.setItem('todoID', todoID);
        getTodo(todoID, updateModal);
    });

    // Hide file form when modal closes
    document.getElementById('descriptionModal')?.addEventListener('hidden.bs.modal', hideAddFilesForm);

    // Save notes
    document.getElementById('saveNotesButton')?.addEventListener('click', () => {
        const todoID = localStorage.getItem('todoID')!;
        const notes = (document.getElementById('descriptionNotes') as HTMLTextAreaElement).value;
        addTodoNotes(todoID, notes);
    });

    // Mark completed
    document.getElementById('completedButton')?.addEventListener('click', () => {
        const todoID = localStorage.getItem('todoID')!;
        completeTodo(todoID).then(markCompleted);
    });

    // Delete todo
    document.getElementById('deleteTodoButton')?.addEventListener('click', () => {
        const todoID = localStorage.getItem('todoID')!;
        const title = document.getElementById('descriptionTitle')?.textContent ?? '';
        if (confirm(`You are about to delete ~${title}~`)) {
            deleteTodo(todoID);
        }
    });

    // Show file upload form
    document.getElementById('showAddFilesButton')?.addEventListener('click', showAddFilesForm);

    // File input change
    document.getElementById('fileinput')?.addEventListener('change', addFileName);

    window.addEventListener('beforeunload', closeChatSession);
});

function updateModal(todo: Todo): void {
    const set = (id: string, value: string) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    set('descriptionTitle', todo.title);
    set('descriptionDescription', todo.description);
    set('descriptionDateDue', todo.dateDue);
    set('descriptionDateCreated', todo.dateCreated);

    const notes = document.getElementById('descriptionNotes') as HTMLTextAreaElement;
    if (notes) notes.value = todo.notes ?? '';

    if (todo.completed) {
        markCompleted();
    } else {
        import('../ui').then(({ markNotCompleted }) => markNotCompleted());
    }
}
