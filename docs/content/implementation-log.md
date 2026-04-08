# Implementation Log — Todo App AWS Chatbot

## Project context

Todo app on AWS with Bedrock AI chatbot. Using this project to learn and document
the full Bedrock ecosystem. Each phase produces blog-ready technical insights.

- Blog post planned: yes
- Steering standards: `application-engineering-steering-standard-v1.0.md`,
  `implementation-content-logging-steering-standard-v1.0.md`

---

## Phase 1 — Chatbot Production Fixes

**Started:** 2026-04-08
**Goal:** Bring chatbot into IaC, fix session bug, add auth, observability, Nova Micro

### Architecture decisions

**Decision: Dual-key single-table DynamoDB for WebSocket session management**

- Date: 2026-04-08
- Context: Need to map `connectionId` → `sessionId` and persist `sessionId` per
  `userID` across reconnects
- Decision: Single BotTable with two item types: `PK=connectionId` and `PK=userID`
- Alternatives considered: GSI on connectionId table, separate SessionsTable
- Trade-off: Two writes on connect vs no GSI cost and simpler IAM
- Blog relevance: Good intro to single-table DynamoDB patterns in serverless

**Decision: Lambda authorizer on $connect (not inline validation)**

- Date: 2026-04-08
- Context: WebSocket $connect needs Cognito JWT validation
- Decision: Separate Lambda authorizer, token passed as `?token=` query param
- Why: WebSocket browsers cannot send custom headers; authorizer is the clean API GW pattern
- Gotcha captured: WebSocket $connect auth cannot use Authorization header from browser —
  must use query string. This differs from HTTP API auth and catches many developers off guard.
- Blog relevance: High — common pain point

**Decision: Amazon Nova Micro over Claude 3.5 Haiku**

- Date: 2026-04-08
- Context: Model upgrade for Bedrock Agent
- Decision: `amazon.nova-micro-v1:0` — cheapest Nova model with tool use support
- Alternatives: Claude 3.5 Haiku (more capable, higher cost), Nova Lite (multimodal)
- Trade-off: Nova Micro is text-only but sufficient for todo CRUD chatbot; significantly cheaper
- Blog relevance: Good cost comparison angle for the article

**Decision: Custom Resource Lambda to enable Bedrock invocation logging**

- Date: 2026-04-08
- Context: No native CloudFormation resource for `put_model_invocation_logging_configuration`
- Decision: SAM Custom Resource Lambda that runs once on stack create/update
- Gotcha: Bedrock model invocation logging has no CloudFormation support —
  requires SDK call, making it invisible if you only use the console
- Blog relevance: High — operational blind spot most tutorials skip

### Critical bugs fixed

**Bug: New session_id per message (context lost between messages)**

- Symptom: Agent had no memory of previous messages in the same conversation
- Root cause: `session_id = str(uuid.uuid1())` called inside `lambda_handler` on every
  invocation — every message started a fresh Bedrock session
- Fix: `sessionId` generated once per user, stored in BotTable, reused across messages
- Blog relevance: High — likely the most common Bedrock Agent integration mistake

**Bug: New WebSocket per message**

- Symptom: 200-400ms overhead per message, unreliable typing indicator
- Root cause: `new WebSocket(...)` called inside `sendMessage()`, connection closed after reply
- Fix: Module-level WebSocket instance, open on chat panel show, close on hide
- Blog relevance: Medium — illustrates stateful vs stateless frontend patterns

**Security gap: No auth on $connect**

- Symptom: Any caller with the WebSocket URL could connect and invoke the Bedrock Agent
- Root cause: `$connect` handler only stored the connectionId, no token validation
- Fix: Lambda authorizer validates Cognito JWT before connection is accepted
- Blog relevance: High — serverless auth gaps are a key security topic

**Security gap: userID sent as payload from frontend**

- Symptom: Frontend sent `{ userID: "email@domain.com", human: "..." }` — PII in WS payload
- Root cause: Backend trusted user-supplied identity instead of JWT claims
- Fix: `userID` read from `$context.authorizer.userID` (set by Lambda authorizer from JWT)
- Blog relevance: High — illustrates trust boundary mistakes in serverless

---

## Strongest blog candidates so far

1. WebSocket + Bedrock: the session persistence bug everyone makes
2. WebSocket $connect auth: why query string, not headers
3. Single-table DynamoDB for WebSocket connection + session tracking
4. Bedrock model invocation logging: the operational blind spot
5. IAM scoping for Bedrock Agents: from `dynamodb:*` to least privilege
