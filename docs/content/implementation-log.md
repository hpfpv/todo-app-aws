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

## Phase 1 — Implementation session (2026-04-09)

**Milestone:** All Lambda handlers, SAM template, samconfig, and frontend changes
implemented and merged into PR.

---

### Gotcha: SAM CLI severely out of date — `--lint` flag unavailable

- Date: 2026-04-09
- Iteration: Phase 1 implementation
- Related area: Tooling / deployment ergonomics
- Trigger: Gotcha
- Observation: `sam validate --lint` failed — installed version is 1.50.0, `--lint`
  was added in a later release (current latest: 1.157.1). Template validation ran
  without linting; cfn-lint checks were skipped.
- Impact: CloudFormation resource-level lint warnings not caught locally before deploy.
- Resolution: Ran `sam validate` without `--lint`; template was structurally valid.
  Upgrade SAM CLI before next deploy cycle.
- Lesson: Pin and validate SAM CLI version in CI (`setup-sam@v2` pulls latest — add
  `version:` pin to the workflow step for reproducible builds).
- Blog relevance: Low — tooling hygiene, not architecturally interesting.
- Tags: `sam`, `tooling`, `ci`

---

### Decision: SAM templates moved to `infra/` subdirectory

- Date: 2026-04-09
- Related area: Infrastructure layout
- Trigger: Design decision (user requirement)
- Decision: `template.yaml` and `samconfig.toml` live under
  `services/ai-assistant/infra/` rather than the service root.
- Why: Separates IaC from application code within the service boundary. Consistent
  with services that may have multiple deployment targets.
- Implication: `CodeUri` paths in template must use `../src/` (relative to template
  file location, not working directory). SAM resolves CodeUri relative to template.
- CI change: `working-directory` in workflow changed from `services/ai-assistant` to
  `services/ai-assistant/infra`.
- Lesson: When moving a SAM template, all `CodeUri` values shift with it. Easy to
  miss — `sam build` will fail with a clear error if paths are wrong.
- Blog relevance: Medium — useful IaC layout pattern for multi-service repos.
- Tags: `sam`, `infrastructure`, `serverless`

---

### Security trade-off: JWT audience validation disabled (`verify_aud: False`)

- Date: 2026-04-09
- Related area: Security / Cognito JWT authorizer
- Trigger: Trade-off / security observation
- Observation: The Lambda authorizer uses `options={'verify_aud': False}` in
  PyJWT decode. This means any valid JWT signed by this Cognito User Pool —
  including tokens issued to other App Clients in the same pool — will be accepted.
- Why the trade-off was made: The `COGNITO_CLIENT_ID` (App Client ID) was not
  included in the plan's env vars, so audience validation was deferred.
- Impact: In a single-pool, single-client setup this is low risk. In a shared pool
  this is a meaningful gap — a token from a different application grants chatbot access.
- Resolution: Flagged in code review. Fix requires adding `COGNITO_CLIENT_ID` as a
  new parameter to the SAM template and GitHub secret. Deferred to Phase 2.
- Also noted: No `token_use` check — Cognito `access_token` would also pass because
  both are signed by the same JWKS. Should verify `payload['token_use'] == 'id'`.
- Lesson: `verify_aud: False` is a common shortcut in Bedrock/WebSocket tutorials
  that skips a meaningful security control. Always plan for the App Client ID at
  architecture time.
- Blog relevance: High — WebSocket auth + Cognito JWT is a frequent tutorial topic
  and this gap is almost never mentioned.
- Tags: `security`, `cognito`, `jwt`, `websocket`, `lambda-authorizer`

---

### Gotcha: `apigatewaymanagementapi` client instantiated inside hot path

- Date: 2026-04-09
- Related area: Serverless / Lambda performance
- Trigger: Code review finding / performance
- Observation: The `post_to_connection` client was created inside `_default()` on
  every WebSocket message, rather than at module scope alongside the DynamoDB and
  Bedrock clients.
- Root cause: `endpoint_url` is dynamic per deployment, so it was read inside the
  function. In fact, `WS_ENDPOINT` is an env var available at module load time.
- Impact: boto3 client initialization adds latency to every message handled by the
  warm function. For a chatbot already waiting on Bedrock Agent (1–5s), this adds
  measurable overhead.
- Fix: Moved to module scope: `_api_gw_mgmt = boto3.client('apigatewaymanagementapi',
  endpoint_url=WS_ENDPOINT) if WS_ENDPOINT else None`.
- Lesson: All boto3 clients that don't depend on per-request values belong at module
  scope. This is a basic Lambda cold-start optimization but easy to miss when
  `endpoint_url` looks like it requires runtime resolution.
- Blog relevance: Medium — good serverless performance checklist item.
- Tags: `lambda`, `serverless`, `performance`, `apigw`, `websocket`

---

### Gotcha: TypeScript `Record<string, unknown>` breaks nested property access

- Date: 2026-04-09
- Related area: Frontend / TypeScript
- Trigger: TypeScript diagnostic error surfaced by IDE hook
- Observation: When guarding `JSON.parse(stored)` with a try/catch, the variable
  was typed as `Record<string, unknown>`. Accessing `tokens?.IdToken?.jwtToken`
  then failed TypeScript compilation — `Property 'jwtToken' does not exist on type
  'unknown'`.
- Fix: Typed the variable with the actual expected shape:
  `{ IdToken?: { jwtToken?: string } }`.
- Lesson: When adding a try/catch around JSON.parse in TypeScript, the type must
  reflect the expected payload shape, not a generic `Record`. The compiler is right
  to reject it — a type-safe parse forces you to acknowledge the shape.
- Blog relevance: Low — routine TypeScript.
- Tags: `typescript`, `frontend`

---

### Observation: `.github/` absent from feature branch — workflows had to be exported from main

- Date: 2026-04-09
- Related area: CI/CD / Git workflow
- Trigger: Gotcha
- Observation: The `chatbot` branch did not contain `.github/workflows/` — those
  files existed only on `main`. The branch history diverged before workflows were
  added. `git checkout main -- .github/` failed because the path was not tracked
  in this branch's index.
- Fix: Used `git show main:.github/workflows/<file>` to export each file to a temp
  path, then copied into the branch and committed.
- Lesson: When a feature branch is long-lived and diverges from main before CI
  files are added, they won't be present. Check for `.github/` when doing branch
  work that touches CI, especially if the branch predates the workflow additions.
- Blog relevance: Low — git housekeeping.
- Tags: `git`, `ci`, `github-actions`

---

### Decision: Frontend pipeline updated for Vite build (apps/web → dist/)

- Date: 2026-04-09
- Related area: CI/CD / Frontend deployment
- Trigger: Architecture change
- Observation: The original `frontend-pipeline.yaml` synced the `frontend/` directory
  directly to S3 (plain HTML/JS, no build step). The new frontend uses Vite +
  TypeScript under `apps/web/`. S3 must receive the compiled `dist/` output.
- Changes made:
  - Path trigger: `frontend/**` → `apps/web/**`
  - Added `actions/setup-node@v4` + `npm ci` + `npm run build`
  - S3 source: `frontend` → `apps/web/dist`
  - CloudFront invalidation: `/index.html /home.html /js/script.js` → `/*`
  - `VITE_CHATBOT_WS_ENDPOINT` injected at build time via GitHub secret
- Lesson: Static S3 deploys and Vite builds are different deployment models. A
  pipeline that worked for raw HTML must be rebuilt — not patched — when a build
  step is introduced. The invalidation path also changes because Vite asset names
  are hashed.
- Blog relevance: Medium — common pattern when migrating from plain HTML to a
  bundled frontend.
- Tags: `ci`, `github-actions`, `vite`, `s3`, `cloudfront`, `frontend`

---

## Strongest blog candidates so far

1. WebSocket + Bedrock: the session persistence bug everyone makes
2. WebSocket $connect auth: why query string, not headers
3. Single-table DynamoDB for WebSocket connection + session tracking
4. Bedrock model invocation logging: the operational blind spot
5. IAM scoping for Bedrock Agents: from `dynamodb:*` to least privilege
