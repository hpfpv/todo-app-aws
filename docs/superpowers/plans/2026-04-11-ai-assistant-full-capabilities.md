# AI Assistant Full Capabilities + Attachments Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the AI assistant complete control over all todo and attachment operations, fix the broken frontend attachment upload flow, and add drag-and-drop file attachment to the AI chat drawer.

**Architecture:** The Bedrock Agent action group Lambda gains access to both the todo DynamoDB table and the files DynamoDB table + S3 bucket, enabling full CRUD over todos and attachments. The frontend attachment flow is completed (S3 direct upload via Cognito Identity credentials → register via attachments API). A new drag-and-drop zone in the chat drawer uploads files to S3 and injects context into the AI conversation so the agent can call `addTodoFile` to register the attachment.

**Tech Stack:** Python 3.12 (Lambda), TypeScript (frontend), AWS Bedrock Agents (FunctionSchema), DynamoDB, S3, Cognito Identity Pool, AWS SAM, Vite

> **Blog note:** The "implementation-content-logging-steering-standard-v1.0" file was not found in the repo or global config. Please provide it before execution or create it at `docs/superpowers/standards/implementation-content-logging-steering-standard-v1.0.md`. Each task below includes an `## Implementation Notes` block (in the plan, not in source) to capture blog-post-worthy context — populate these during execution.

---

## File Map

| File | Change | Reason |
|------|--------|--------|
| `services/ai-assistant/src/action_group/handler.py` | Modify | Add deleteTodo, listTodoFiles, addTodoFile, deleteTodoFile actions |
| `infra/sam/ai-assistant/template.yaml` | Modify | Add 4 new agent functions; add IAM perms for files table + S3 |
| `apps/web/src/api.ts` | Modify | Add getTodoFiles, addTodoFile, deleteTodoFile client functions |
| `apps/web/src/types.ts` | Modify | Add TodoFile type (if not already defined) |
| `apps/web/src/pages/home.ts` | Modify | Wire attachment load on modal open, upload submit, delete handler |
| `apps/web/src/chatbot.ts` | Modify | Add drag-and-drop zone, S3 upload, file context injection |
| `apps/web/src/ui.ts` | Modify | Add renderFiles, renderFileRow, showFileUploading functions |

---

## Context

### Attachment service API
- `GET  /{todoID}/files` → list files for a todo
- `POST /{todoID}/files/upload` body `{fileName, filePath}` where `filePath` is the S3 object key
- `DELETE /{todoID}/files/{fileID}/delete` body `{filePath}` where `filePath` is the CDN URL

### S3 Upload flow (Cognito Identity Pool)
The Identity Pool ID is available at `config.cognitoIdentityPoolId` (env `VITE_COGNITO_IDENTITY_POOL_ID`).
Use `@aws-sdk/client-s3` with temporary credentials from `@aws-sdk/credential-providers` `fromCognitoIdentityPool`.
S3 key pattern: `{userID}/{todoID}/{uuid}-{fileName}`.

### Action group current functions
`getTodos`, `getTodo`, `addTodo`, `completeTodo`, `addTodoNotes` — all in `services/ai-assistant/src/action_group/handler.py`.

### AI assistant SAM imports needed (add to template)
- `todo-houessou-com-attachments-service-TodoFilesTable`
- `todo-houessou-com-attachments-service-TodoFilesTableArn`
- `todo-houessou-com-attachments-service-TodoFilesBucket`
- `todo-houessou-com-attachments-service-TodoFilesBucketArn`

---

## Task 1 — AI Action Group: Add Attachment + Delete Actions

**Files:**
- Modify: `services/ai-assistant/src/action_group/handler.py`

- [ ] **Step 1.1 — Add imports and env vars at top of handler**

Replace the top of the file (after existing imports) with:

```python
import boto3
import json
import logging
import os
import uuid
from datetime import datetime

client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
files_client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
s3_client = boto3.client('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

TODO_TABLE = os.environ['TODO_TABLE']
FILES_TABLE = os.environ.get('FILES_TABLE', '')
FILES_BUCKET = os.environ.get('FILES_BUCKET', '')
FILES_BUCKET_CDN = os.environ.get('FILES_BUCKET_CDN', '')
```

- [ ] **Step 1.2 — Add deleteTodo function**

After the existing `addTodoNotes` function, add:

```python
def deleteTodo(userID, todoID):
    # Delete all associated files first
    if FILES_TABLE:
        resp = files_client.query(
            TableName=FILES_TABLE,
            IndexName='todoIDIndex',
            KeyConditions={
                'todoID': {
                    'AttributeValueList': [{'S': todoID}],
                    'ComparisonOperator': 'EQ',
                }
            },
        )
        for item in resp.get('Items', []):
            file_id = item['fileID']['S']
            file_path = item['filePath']['S']
            # Delete from S3
            if FILES_BUCKET and FILES_BUCKET_CDN:
                s3_key = file_path.replace(f'https://{FILES_BUCKET_CDN}/', '').replace('%40', '@')
                try:
                    s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
                except Exception as e:
                    logger.warning(json.dumps({'action': 'deleteTodo_s3_warn', 'fileID': file_id, 'error': str(e)}))
            # Delete from files table
            files_client.delete_item(
                TableName=FILES_TABLE,
                Key={'fileID': {'S': file_id}},
            )
    # Delete the todo
    client.delete_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
    )
    logger.info(json.dumps({'action': 'deleteTodo', 'userID': userID[:3] + '***', 'todoID': todoID}))
    return json.dumps({'status': 'success'})
```

- [ ] **Step 1.3 — Add listTodoFiles function**

```python
def listTodoFiles(todoID):
    if not FILES_TABLE:
        return {'files': []}
    resp = files_client.query(
        TableName=FILES_TABLE,
        IndexName='todoIDIndex',
        KeyConditions={
            'todoID': {
                'AttributeValueList': [{'S': todoID}],
                'ComparisonOperator': 'EQ',
            }
        },
    )
    files = [
        {
            'fileID': item['fileID']['S'],
            'fileName': item['fileName']['S'],
            'filePath': item['filePath']['S'],
        }
        for item in resp.get('Items', [])
    ]
    logger.info(json.dumps({'action': 'listTodoFiles', 'todoID': todoID, 'count': len(files)}))
    return {'files': files}
```

- [ ] **Step 1.4 — Add addTodoFile function**

```python
def addTodoFile(todoID, fileName, fileUrl):
    """Register a file that has already been uploaded to S3/CDN."""
    if not FILES_TABLE:
        return json.dumps({'error': 'Files service not configured'})
    file_id = str(uuid.uuid4())
    files_client.put_item(
        TableName=FILES_TABLE,
        Item={
            'fileID': {'S': file_id},
            'todoID': {'S': todoID},
            'fileName': {'S': fileName},
            'filePath': {'S': fileUrl},
        },
    )
    logger.info(json.dumps({'action': 'addTodoFile', 'todoID': todoID, 'fileName': fileName}))
    return json.dumps({'status': 'success', 'fileID': file_id})
```

- [ ] **Step 1.5 — Add deleteTodoFile function**

```python
def deleteTodoFile(todoID, fileID):
    if not FILES_TABLE:
        return json.dumps({'error': 'Files service not configured'})
    # Get file record to find S3 key
    resp = files_client.get_item(
        TableName=FILES_TABLE,
        Key={'fileID': {'S': fileID}},
    )
    item = resp.get('Item')
    if item:
        file_path = item['filePath']['S']
        if FILES_BUCKET and FILES_BUCKET_CDN:
            s3_key = file_path.replace(f'https://{FILES_BUCKET_CDN}/', '').replace('%40', '@')
            try:
                s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
            except Exception as e:
                logger.warning(json.dumps({'action': 'deleteTodoFile_s3_warn', 'fileID': fileID, 'error': str(e)}))
        files_client.delete_item(
            TableName=FILES_TABLE,
            Key={'fileID': {'S': fileID}},
        )
    logger.info(json.dumps({'action': 'deleteTodoFile', 'todoID': todoID, 'fileID': fileID}))
    return json.dumps({'status': 'success'})
```

- [ ] **Step 1.6 — Update lambda_handler to route new functions**

In `lambda_handler`, add after the existing `elif function == 'completeTodo':` block:

```python
    elif function == 'deleteTodo':
        body = deleteTodo(parameters['userID'], parameters['todoID'])
    elif function == 'listTodoFiles':
        body = listTodoFiles(parameters['todoID'])
    elif function == 'addTodoFile':
        body = addTodoFile(parameters['todoID'], parameters['fileName'], parameters['fileUrl'])
    elif function == 'deleteTodoFile':
        body = deleteTodoFile(parameters['todoID'], parameters['fileID'])
```

- [ ] **Step 1.7 — Commit**

```bash
git add services/ai-assistant/src/action_group/handler.py
git commit -m "feat(ai-assistant): add deleteTodo, listTodoFiles, addTodoFile, deleteTodoFile actions"
```

---

## Task 2 — AI Assistant SAM Template: New Functions + Permissions

**Files:**
- Modify: `infra/sam/ai-assistant/template.yaml`

- [ ] **Step 2.1 — Add env vars to ActionGroupHandlerFunction**

Under `ActionGroupHandlerFunction > Properties > Environment > Variables`, add:

```yaml
          FILES_TABLE: !ImportValue "todo-houessou-com-attachments-service-TodoFilesTable"
          FILES_BUCKET: !ImportValue "todo-houessou-com-attachments-service-TodoFilesBucket"
          FILES_BUCKET_CDN: !Sub "{{resolve:ssm:/todo-houessou-com/attachments-service/cdn-domain}}"
```

> **NOTE:** If the CDN domain is not in SSM, export it from the attachments-service stack first, then import it here. Alternatively hard-code the CloudFront domain as a Parameter.

Add a Parameter to expose CDN domain if not already exported:

At the top `Parameters` section, add:
```yaml
  TodoFilesBucketCDN:
    Type: String
    Description: CloudFront domain for todo files (e.g. d1234.cloudfront.net)
```

Then use `!Ref TodoFilesBucketCDN` for `FILES_BUCKET_CDN`.

- [ ] **Step 2.2 — Add IAM permissions for files table and S3**

Under `ActionGroupHandlerFunction > Properties > Policies`, extend the Statement list:

```yaml
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:Query
                - dynamodb:PutItem
                - dynamodb:DeleteItem
              Resource:
                - !ImportValue "todo-houessou-com-attachments-service-TodoFilesTableArn"
                - !Sub
                  - "${TableArn}/index/*"
                  - TableArn: !ImportValue "todo-houessou-com-attachments-service-TodoFilesTableArn"
            - Effect: Allow
              Action:
                - s3:DeleteObject
                - s3:GetObject
              Resource:
                - !Sub
                  - "${BucketArn}/*"
                  - BucketArn: !ImportValue "todo-houessou-com-attachments-service-TodoFilesBucketArn"
```

Also update `TodoAgentRole > Policies > BedrockAgentPolicy > Statement` to allow `InvokeFunction` on the action group (already there via `!GetAtt ActionGroupHandlerFunction.Arn`).

- [ ] **Step 2.3 — Add 4 new agent functions to the FunctionSchema in TodoAgent**

Under `TodoAgent > Properties > ActionGroups[0] > FunctionSchema > Functions`, add after `completeTodo`:

```yaml
              - Name: deleteTodo
                Description: Delete a todo and all its attachments
                Parameters:
                  userID:
                    Type: string
                    Description: The user's ID
                    Required: true
                  todoID:
                    Type: string
                    Description: The todo's ID
                    Required: true
              - Name: listTodoFiles
                Description: List all file attachments for a specific todo
                Parameters:
                  todoID:
                    Type: string
                    Description: The todo's ID
                    Required: true
              - Name: addTodoFile
                Description: Register a file that has already been uploaded to storage as an attachment on a todo
                Parameters:
                  todoID:
                    Type: string
                    Description: The todo's ID
                    Required: true
                  fileName:
                    Type: string
                    Description: Display name of the file
                    Required: true
                  fileUrl:
                    Type: string
                    Description: The CDN or storage URL of the uploaded file
                    Required: true
              - Name: deleteTodoFile
                Description: Delete a file attachment from a todo
                Parameters:
                  todoID:
                    Type: string
                    Description: The todo's ID
                    Required: true
                  fileID:
                    Type: string
                    Description: The file's ID
                    Required: true
```

- [ ] **Step 2.4 — Update the agent instruction to mention attachments capability**

Replace the `Instruction` block with:

```yaml
      Instruction: |
        You are a helpful assistant for a todo list application called TodoHouessou.
        The user's ID is provided at the start of each message in the format <userid>USER_ID</userid>.
        Always extract and use this userID when calling API actions that require it.
        You can help users:
        - List, view, create, complete, and delete todos
        - Add and update notes on todos
        - List, add, and delete file attachments on todos
        When a user uploads a file via drag-and-drop, they will tell you the file URL and name. Ask which todo to attach it to if not specified.
        When referring to todos or files, use natural language. Never expose internal IDs unless the user asks.
        Always respond concisely and in a friendly tone.
```

- [ ] **Step 2.5 — Commit**

```bash
git add infra/sam/ai-assistant/template.yaml
git commit -m "feat(ai-assistant): add attachment actions to Bedrock agent + IAM permissions"
```

---

## Task 3 — Frontend: Complete Attachment API Client

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`

- [ ] **Step 3.1 — Add TodoFile type to types.ts**

Open `apps/web/src/types.ts`. Add:

```typescript
export interface TodoFile {
    fileID: string;
    todoID: string;
    fileName: string;
    filePath: string;
}

export interface FilesResponse {
    files: TodoFile[];
}
```

- [ ] **Step 3.2 — Add files API functions to api.ts**

Add to `apps/web/src/api.ts`:

```typescript
import { config } from './config';
import { Todo, TodosResponse, TodoFile, FilesResponse } from './types';

export async function getTodoFiles(todoID: string): Promise<TodoFile[]> {
    const url = `${config.filesApiEndpoint}${todoID}/files`;
    const data = await apiFetch<FilesResponse>(url);
    return data?.files ?? [];
}

export async function registerTodoFile(todoID: string, fileName: string, filePath: string): Promise<boolean> {
    const url = `${config.filesApiEndpoint}${todoID}/files/upload`;
    const options: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileName, filePath }),
    };
    const data = await apiFetch<{ status: string }>(url, options);
    return data?.status === 'success';
}

export async function deleteTodoFile(todoID: string, fileID: string, filePath: string): Promise<boolean> {
    const url = `${config.filesApiEndpoint}${todoID}/files/${fileID}/delete`;
    const options: RequestInit = {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filePath }),
    };
    const data = await apiFetch<{ status: string }>(url, options);
    return data?.status === 'success';
}
```

- [ ] **Step 3.3 — Commit**

```bash
git add apps/web/src/api.ts apps/web/src/types.ts
git commit -m "feat(frontend): add getTodoFiles, registerTodoFile, deleteTodoFile API client functions"
```

---

## Task 4 — Frontend: Wire Attachment UI in Todo Modal

**Files:**
- Modify: `apps/web/src/pages/home.ts`
- Modify: `apps/web/src/ui.ts`

**Context:** The modal (`descriptionModal`) opens when a todo card's Open button is clicked. `todoID` is stored in `localStorage.setItem('todoID', todoID)`. Files should load alongside the todo detail. The existing `showAddFilesForm` / `addFileName` / `hideAddFilesForm` functions in `ui.ts` show a file input but do not upload.

- [ ] **Step 4.1 — Add renderFiles and deleteFile UI helpers to ui.ts**

In `apps/web/src/ui.ts`, add:

```typescript
export function renderFiles(files: import('./types').TodoFile[]): void {
    const container = document.getElementById('filesList');
    if (!container) return;
    container.innerHTML = '';
    if (files.length === 0) {
        container.innerHTML = '<p class="text-muted small">No attachments</p>';
        return;
    }
    files.forEach(f => {
        const row = document.createElement('div');
        row.className = 'd-flex align-items-center justify-content-between mb-1';
        row.dataset.fileid = f.fileID;
        row.dataset.filepath = f.filePath;
        row.innerHTML = `
            <a href="${f.filePath}" target="_blank" class="text-truncate mr-2" style="max-width:200px">${f.fileName}</a>
            <button class="btn btn-sm btn-outline-danger delete-file-btn" data-fileid="${f.fileID}" data-filepath="${f.filePath}">✕</button>
        `;
        container.appendChild(row);
    });
}

export function showFileUploading(fileName: string): void {
    const container = document.getElementById('filesList');
    if (!container) return;
    const el = document.createElement('div');
    el.id = 'uploadingIndicator';
    el.className = 'text-muted small';
    el.textContent = `Uploading ${fileName}…`;
    container.appendChild(el);
}

export function hideFileUploading(): void {
    document.getElementById('uploadingIndicator')?.remove();
}
```

- [ ] **Step 4.2 — Add S3 upload helper (new file)**

Create `apps/web/src/s3upload.ts`:

```typescript
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';
import { config } from './config';

export async function uploadToS3(file: File, todoID: string): Promise<string> {
    const userID = localStorage.getItem('userID') ?? 'unknown';
    const key = `${userID}/${todoID}/${crypto.randomUUID()}-${file.name}`;

    const credentials = fromCognitoIdentityPool({
        clientConfig: { region: config.awsRegion },
        identityPoolId: config.cognitoIdentityPoolId,
    });

    const s3 = new S3Client({
        region: config.awsRegion,
        credentials,
    });

    await s3.send(new PutObjectCommand({
        Bucket: config.s3Bucket,
        Key: key,
        Body: file,
        ContentType: file.type,
    }));

    // Return the S3 key (not full URL) — the attachments API converts it to CDN URL
    return key;
}
```

> **Note:** Install the SDK packages:
> ```bash
> cd apps/web && npm install @aws-sdk/client-s3 @aws-sdk/credential-providers
> ```

- [ ] **Step 4.3 — Wire file load and upload in home.ts**

In `apps/web/src/pages/home.ts`, add the following to the `updateModal` function (after populating notes):

```typescript
// Load files for this todo
import('../api').then(({ getTodoFiles }) => {
    getTodoFiles(todo.todoID).then(files => {
        import('../ui').then(({ renderFiles }) => renderFiles(files));
    });
});
```

Add a file upload submit handler (inside `DOMContentLoaded`):

```typescript
// Upload attachment button
document.getElementById('uploadFileButton')?.addEventListener('click', async () => {
    const todoID = localStorage.getItem('todoID');
    if (!todoID) return;
    const input = document.getElementById('fileinput') as HTMLInputElement;
    const file = input?.files?.[0];
    if (!file) return;

    const { showFileUploading, hideFileUploading, renderFiles } = await import('../ui');
    showFileUploading(file.name);

    const { uploadToS3 } = await import('../s3upload');
    const { registerTodoFile, getTodoFiles } = await import('../api');

    const key = await uploadToS3(file, todoID);
    await registerTodoFile(todoID, file.name, key);

    hideFileUploading();
    const files = await getTodoFiles(todoID);
    renderFiles(files);
    input.value = '';
});
```

Add a delete file handler (event delegation on `filesList`):

```typescript
document.getElementById('filesList')?.addEventListener('click', async (e: MouseEvent) => {
    const btn = (e.target as HTMLElement).closest('.delete-file-btn') as HTMLElement | null;
    if (!btn) return;
    const fileID = btn.dataset.fileid!;
    const filePath = btn.dataset.filepath!;
    const todoID = localStorage.getItem('todoID')!;
    if (!confirm('Delete this attachment?')) return;
    const { deleteTodoFile } = await import('../api');
    const { getTodoFiles, renderFiles } = await import('../ui');
    await deleteTodoFile(todoID, fileID, filePath);
    const files = await (await import('../api')).getTodoFiles(todoID);
    renderFiles(files);
});
```

- [ ] **Step 4.4 — Add `filesList` container and `uploadFileButton` to modal HTML**

Find the modal HTML (likely `apps/web/index.html` or a modal partial). Inside the `descriptionModal`, after the `+ Attachment` button add:

```html
<div id="filesList" class="mt-2"></div>
```

Change the `+ Attachment` button to have `id="uploadFileButton"`:
```html
<button id="uploadFileButton" type="button" class="btn btn-outline-secondary btn-sm">+ Attachment</button>
```

- [ ] **Step 4.5 — Commit**

```bash
git add apps/web/src/ui.ts apps/web/src/s3upload.ts apps/web/src/pages/home.ts apps/web/index.html
git commit -m "feat(frontend): wire attachment upload, list, and delete in todo modal"
```

---

## Task 5 — Frontend: Drag-and-Drop File to AI Chat Drawer

**Files:**
- Modify: `apps/web/src/chatbot.ts`

**Context:** The chat drawer has `id="chatDrawer"`. The user drops a file → frontend uploads to S3 → injects a system message into the chat and sends context to the AI so it can call `addTodoFile`.

- [ ] **Step 5.1 — Add drag-and-drop handlers to chatbot.ts**

Add to `apps/web/src/chatbot.ts`:

```typescript
let pendingFileUrl: string | null = null;
let pendingFileName: string | null = null;

export function initChatDropZone(): void {
    const drawer = document.getElementById('chatDrawer');
    if (!drawer) return;

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

        displayMessage(`📎 Uploading ${file.name}…`, 'bot', false);
        displayTypingIndicator();

        try {
            const { uploadToS3 } = await import('./s3upload');
            const { config } = await import('./config');
            const todoID = localStorage.getItem('todoID') ?? '';
            const key = await uploadToS3(file, todoID || 'unassigned');
            const fileUrl = `https://${config.cdnDomain}/${key}`;

            pendingFileUrl = fileUrl;
            pendingFileName = file.name;

            removeTypingIndicator();
            displayMessage(
                `📎 File "${file.name}" uploaded. I'll ask the AI to attach it to a todo.`,
                'bot',
                false,
            );

            // Send context to AI
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
```

- [ ] **Step 5.2 — Call initChatDropZone from openDrawer in home.ts**

In `apps/web/src/pages/home.ts`, update `openDrawer`:

```typescript
import { sendMessage, openChatSession, closeChatSession, restoreChatHistory, clearChatHistory, initChatDropZone } from '../chatbot';

function openDrawer(): void {
    if (!chatDrawer || !chatFab) return;
    chatDrawer.classList.add('open');
    chatFab.style.display = 'none';
    openChatSession();
    initChatDropZone();
    (document.getElementById('userInput') as HTMLInputElement)?.focus();
}
```

- [ ] **Step 5.3 — Add drag-over CSS to chat drawer styles**

In the relevant CSS file (search for `#chatDrawer` styles), add:

```css
#chatDrawer.drag-over {
    border: 2px dashed var(--color-primary, #2d7d6f);
    background-color: rgba(45, 125, 111, 0.05);
}
```

- [ ] **Step 5.4 — Add cdnDomain to config**

In `apps/web/src/config.ts`, add `cdnDomain` sourced from `import.meta.env.VITE_CDN_DOMAIN`.
In CI/CD (GitHub Actions), set `VITE_CDN_DOMAIN` to the CloudFront domain (get from attachments-service stack output `TodoFilesBucketCFDomain` or equivalent).

- [ ] **Step 5.5 — Commit**

```bash
git add apps/web/src/chatbot.ts apps/web/src/pages/home.ts apps/web/src/config.ts
git commit -m "feat(frontend): add drag-and-drop file upload to AI chat drawer"
```

---

## Task 6 — Deploy and Validate

- [ ] **Step 6.1 — Build and verify frontend compiles**

```bash
cd apps/web && npm install && npm run build
```
Expected: Build completes with no TypeScript errors.

- [ ] **Step 6.2 — Deploy AI assistant stack (CI or manual)**

```bash
cd infra/sam/ai-assistant
sam build && sam deploy --no-confirm-changeset
```
Expected: Stack UPDATE_COMPLETE. Verify new agent is re-prepared (PREPARED status).

- [ ] **Step 6.3 — Manual smoke test: AI assistant full actions**

In the chat drawer:
1. "list my todos" → should list todos ✓
2. "create a todo: test attachments, test attachment feature, due tomorrow" → should confirm creation ✓
3. "list files for todo test attachments" → should return empty list ✓
4. "delete todo test attachments" → should confirm deletion ✓

- [ ] **Step 6.4 — Manual smoke test: Attachment upload in modal**

1. Open any todo → modal shows `No attachments`
2. Click `+ Attachment` → file picker opens
3. Select a file → file uploads to S3, registers via API, appears in file list
4. Click ✕ on the file → file is deleted from list

- [ ] **Step 6.5 — Manual smoke test: Drag-and-drop to chat**

1. Open chat drawer
2. Drag a file into the drawer
3. File uploads → AI asks which todo to attach it to
4. Reply with todo name → AI calls `addTodoFile` → confirm file appears on that todo

- [ ] **Step 6.6 — Final commit if any cleanup needed**

```bash
git add -p   # review and stage only relevant changes
git commit -m "chore(ai-assistant): post-deploy cleanup and validation"
```

---

## Implementation Notes Template (for Blog Post)

> Fill in each section during execution. These are for the blog post.

### What we built
- Full CRUD for todos via AI chat (list, view, create, complete, delete, add notes)
- Attachment management via AI chat (list, add, delete files)
- Fixed frontend attachment upload flow (S3 direct upload via Cognito Identity)
- Drag-and-drop files into AI chat drawer

### Key architectural decisions
- Action group Lambda now holds access to both the todo table and the files DynamoDB table + S3 bucket
- `addTodoFile` takes a CDN URL so the AI doesn't need to handle S3 presigned URLs
- Drag-and-drop uses the same S3 upload path as the modal, sharing `s3upload.ts`
- Bedrock Agent FunctionSchema cleanly separates todo and file operations

### Gotchas / Lessons Learned
- nova-lite v1 struggles with large action group responses → use slim payloads (getTodos returns only title, dateDue, completed)
- Cognito Identity Pool credentials are needed for direct S3 upload from the browser
- The Bedrock Agent alias must point to a newly prepared version after adding functions

---

*Plan created: 2026-04-11*
*Context: AI assistant returning empty/refusal responses fixed by slimming getTodos payload. Now expanding to full capabilities.*
