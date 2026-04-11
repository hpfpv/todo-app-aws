import { Todo, TodoFile } from './types';

  function getElement(id: string): HTMLElement | null {
      return document.getElementById(id);
  }

  function toggleClass(id: string, addClass: string, removeClass: string): void {
      const el = getElement(id);
      if (!el) return;
      el.classList.add(addClass);
      el.classList.remove(removeClass);
  }

  export function markCompleted(): void {
      toggleClass('completedButton', 'd-none', '');
      toggleClass('alreadyCompletedButton', '', 'd-none');
  }

  export function markNotCompleted(): void {
      toggleClass('completedButton', '', 'd-none');
      toggleClass('alreadyCompletedButton', 'd-none', '');
  }

  export function markFileDeleted(fileID: string): void {
      const el = getElement(fileID);
      if (el) el.classList.add('d-none');
  }

  export function showAddFilesForm(): void {
      const form = getElement('addFilesForm');
      if (form) form.classList.remove('d-none');
  }

  export function hideAddFilesForm(): void {
      const form = getElement('addFilesForm');
      if (form) form.classList.add('d-none');

      const fileInput = getElement('fileinput') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
  }

  export function addFileName(): void {
      const fileInput = getElement('fileinput') as HTMLInputElement;
      const fileNameEl = getElement('fileName');
      if (fileInput?.files?.[0] && fileNameEl) {
          fileNameEl.textContent = fileInput.files[0].name;
      }
  }

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

  export function renderFiles(files: TodoFile[]): void {
      const list = getElement('filesList');
      if (!list) return;
      list.innerHTML = files.map(file => `
          <div id="${file.fileID}">
              <a href="${file.filePath}" target="_blank">${file.fileName}</a>
          </div>
      `).join('');
  }