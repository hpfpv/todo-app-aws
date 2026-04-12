# Blog Input Summary — Todo App AWS Chatbot

Last updated: 2026-04-12
Phase: 1 complete (IaC, auth, session persistence, observability, Nova Micro)
Phase 2 complete (attachments, AI action group, drag-and-drop, CDN)

---

## Strongest insights (high blog value)

### 1. The session persistence bug everyone makes with Bedrock Agents

`session_id = str(uuid.uuid1())` called inside `lambda_handler` on every invocation.
Every message started a fresh Bedrock session — the agent had no memory.
Fix: generate `sessionId` once per user, persist in DynamoDB, reuse across messages.

**Why it matters:** This is almost certainly the most common Bedrock Agent integration
mistake. The Bedrock docs show `sessionId` as a parameter but don't warn that reusing
it is what makes multi-turn conversation work.

**Blog angle:** "The one-line Bedrock Agent bug that kills conversation context"

---

### 2. WebSocket $connect auth: why you must use query string, not headers

Browser WebSocket API (`new WebSocket(url)`) does not allow custom headers on the
upgrade request. API Gateway Lambda authorizers on `$connect` must use query string
parameters to receive the JWT (`?token=...`).

This differs from HTTP API auth and catches developers used to REST auth patterns.

**Security implication:** The token appears in server access logs and browser history.
Cognito ID tokens expire in 1 hour which limits exposure, but API GW access logging
should exclude query strings in production.

**Blog angle:** "WebSocket authentication on AWS: the header that doesn't work"

---

### 3. `verify_aud: False` — the JWT shortcut that skips a real security control

A common shortcut in tutorials: skip audience verification because you don't know
the App Client ID at code-write time. In a single-pool, single-client setup this is
low risk. In a shared pool it means any token from any application in that pool
grants access. Cognito also issues `access_token` signed by the same JWKS — without
a `token_use` check, access tokens also pass.

**Blog angle:** "What most Bedrock WebSocket auth tutorials get wrong"

---

### 4. Bedrock model invocation logging: the operational blind spot

`put_model_invocation_logging_configuration` has no native CloudFormation support.
The only IaC-friendly way is a Custom Resource Lambda. Without this, Bedrock calls
are invisible in CloudWatch — no latency, no token count, no prompt/response audit.

Most tutorials skip it entirely. The CloudFormation gap means it's never set up
automatically even when people mean to.

**Blog angle:** "Bedrock in production: the observability step tutorials always skip"

---

### 5. Single-table DynamoDB for WebSocket connection + session tracking

Two item types in one table: `PK=connectionId` (deleted on disconnect) and
`PK=userID` (survives disconnect, 30-min TTL). On reconnect the `userID` item is
checked for a valid TTL and the `sessionId` is reused — the Bedrock Agent resumes
the conversation.

Alternatives (GSI, separate table) add cost or complexity. The dual-key pattern
keeps IAM narrow: `GetItem`, `PutItem`, `DeleteItem` on one table ARN.

**Blog angle:** "DynamoDB single-table design for WebSocket session state"

---

### 6. IAM scoping for Bedrock Agent invocation

Common mistake: `bedrock:InvokeAgent` on `*`. Correct scope:
`arn:aws:bedrock:{region}:{account}:agent-alias/{agentId}/{aliasId}`.
Same for `execute-api:ManageConnections` — scoped to the specific stage and
`POST/@connections/*`, not `*`.

**Blog angle:** "Least-privilege IAM for Bedrock Agents — the patterns that matter"

---

### 7. boto3 clients belong at module scope — including `apigatewaymanagementapi`

The `post_to_connection` client was created inside the message handler on every
invocation because `endpoint_url` looked like a runtime value. It's actually an
env var available at module load. Moving it to module scope removes per-invocation
client initialization overhead on every message.

**Blog angle:** Sidebar/checklist item in a Lambda performance patterns post.

---

## Suggested blog angles

1. **"Building a production-ready Bedrock Agent chatbot on AWS: what the tutorials
   don't tell you"** — umbrella post covering session persistence bug, auth, logging
2. **"WebSocket authentication on API Gateway: the query string you didn't want to use"**
   — focused on the header limitation and security mitigations
3. **"Bedrock Agent in production: observability, session state, and IAM"**
   — operational focus, covering logging gap, DynamoDB design, IAM scoping
4. **"From plain HTML to Vite + TypeScript: migrating a frontend pipeline on AWS"**
   — lighter post on the frontend modernization side

---

### 8. SAM `--resolve-s3` vs explicit S3 bucket: the region trap

Deploying a SAM stack with `--s3-bucket <bucket-in-region-A>` and `--region <region-B>` causes CloudFormation to fail fetching Lambda code with `AuthorizationHeaderMalformed`. The bucket signing region and the deploy region must match. `--resolve-s3` eliminates this — SAM creates/uses a managed bucket in the target region automatically.

**Blog angle:** "The SAM deployment error that looks like an IAM problem but isn't"

---

### 9. addTodoFile design: AI agents work better with CDN URLs than presigned URLs

When the frontend uploads a file and needs the AI agent to register it, pass the final CDN URL — not a presigned S3 URL or S3 key. Presigned URLs expire and add complexity to the agent's action schema. CDN URLs are stable, short, and require no AWS credentials to resolve.

**Blog angle:** Sidebar in "Designing clean AI agent action schemas"

---

---

### 10. Bedrock Agent context memory: with and without the Memory feature

**Context (Phase 2 — current state):**
The app uses session-scoped context only — no Bedrock Agent Memory feature activated.
On each `invoke_agent` call, Bedrock constructs the model prompt as:

```
[agent instruction]        ← always included
[action group schemas]     ← always included
[recent conversation turns]  ← sliding window, oldest dropped when limit hit
[current user message]
```

The agent "remembers" within a session because the full turn history is replayed
to the model on each invocation. This is standard conversational state, not memory.

**What happens when history exceeds the model's context window:**
Bedrock silently drops the oldest turns from the reconstructed prompt. The session ID
and TTL are unaffected. No error is surfaced — the agent simply loses early context.
For task-oriented sessions (list todos, create a todo, attach a file) this is rarely
a problem, but for long sessions or sessions where early context matters (user
preferences, earlier decisions), facts get lost silently.

**Phase 3 plan — activating Bedrock Agent Memory:**
The Memory feature solves this by periodically summarizing old turns into a compressed
memory store. On future invocations Bedrock injects a summary of older context instead
of the raw turns, so long-term facts survive context truncation.

SAM template change to enable it:
```yaml
# On the agent alias resource
AgentAliasMemoryConfiguration:
  EnabledMemoryTypes:
    - SESSION_SUMMARY
```

The DynamoDB session table design stays the same — Bedrock manages the memory store
internally.

**Blog angle:**
- Part A (current): "How Bedrock Agents handle conversation context without Memory —
  and what breaks at scale"
- Part B (after Phase 3): "Activating Bedrock Agent Memory: one config change, real
  before/after comparison"
- Together they form a complete two-part post showing the evolution from stateless
  session replay → summarised long-term memory, with the same app as the through-line.

**Key contrast points to capture for the post:**
| | Without Memory | With Memory |
|---|---|---|
| Context scope | Current session only | Across sessions |
| Long conv handling | Silent truncation (oldest dropped) | Summarised, injected as context |
| Cross-session recall | None (new sessionId = blank slate) | Preserved facts survive logout/re-login |
| SAM config | None | `SESSION_SUMMARY` on alias |
| Cost | Base invocation only | + memory storage/retrieval calls |
| Useful when | Short, task-focused sessions | Long sessions, returning users, preferences |

---

## Open questions / unresolved items

- `verify_aud: False` — needs `COGNITO_CLIENT_ID` added as parameter before production
- `token_use` check not implemented — access_token would currently pass authorizer
- `deleteTodo` not in action group — confirm if Bedrock Agent schema includes delete path
- SAM CLI needs upgrade — `--lint` not available on installed version (1.50.0)
- Tasks 9 and 12 pending — need deploy output for WebSocket endpoint and frontend config
