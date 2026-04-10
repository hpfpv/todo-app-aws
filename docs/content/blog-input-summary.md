# Blog Input Summary — Todo App AWS Chatbot

Last updated: 2026-04-09
Phase: 1 complete (IaC, auth, session persistence, observability, Nova Micro)

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

## Open questions / unresolved items

- `verify_aud: False` — needs `COGNITO_CLIENT_ID` added as parameter before production
- `token_use` check not implemented — access_token would currently pass authorizer
- `deleteTodo` not in action group — confirm if Bedrock Agent schema includes delete path
- SAM CLI needs upgrade — `--lint` not available on installed version (1.50.0)
- Tasks 9 and 12 pending — need deploy output for WebSocket endpoint and frontend config
