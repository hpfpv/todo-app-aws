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

  export function renderFiles(files: TodoFile[]): void {
      const list = getElement('filesList');
      if (!list) return;
      list.innerHTML = files.map(file => `
          <div id="${file.fileID}">
              <a href="${file.filePath}" target="_blank">${file.fileName}</a>
          </div>
      `).join('');
  }