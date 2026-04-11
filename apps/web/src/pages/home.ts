import { getTodos, getTodo, addTodo, completeTodo, deleteTodo, addTodoNotes } from '../api';
import { logOut } from '../auth';
import { sendMessage, openChatSession, closeChatSession, restoreChatHistory, clearChatHistory } from '../chatbot';
import { renderTodos, markCompleted, showAddFilesForm, hideAddFilesForm, addFileName } from '../ui';
import { Todo } from '../types';

document.addEventListener('DOMContentLoaded', () => {

    // Load todos on page load
    getTodos(renderTodos);

    // Restore chat history from previous session
    restoreChatHistory();

    // Sign out button — clear chat history before logging out
    document.getElementById('signOutButton')?.addEventListener('click', () => {
        clearChatHistory();
        logOut();
    });

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

    // Capture todoID on card Open button click (Bootstrap 4 does not set relatedTarget on native DOM events)
    document.getElementById('todosList')?.addEventListener('click', (e: MouseEvent) => {
        const btn = (e.target as HTMLElement).closest('[data-todoid]') as HTMLElement | null;
        if (btn?.dataset?.todoid) {
            localStorage.setItem('todoID', btn.dataset.todoid);
        }
    });

    // Description modal — load todo details when opened
    document.getElementById('descriptionModal')?.addEventListener('show.bs.modal', () => {
        const todoID = localStorage.getItem('todoID');
        if (!todoID) return;
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
