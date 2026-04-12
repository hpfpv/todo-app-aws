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

---

## Phase 1 — CI/CD overhaul session (2026-04-10)

**Milestone:** All pipelines overhauled, infra restructured, merged to main and
first pipeline run attempted.

---

### Decision: Consolidate all SAM templates under `infra/sam/<service>/`

- Date: 2026-04-10
- Related area: Infrastructure layout
- Trigger: Design decision (user requirement)
- Decision: Move all SAM `template.yaml` and `samconfig.toml` files out of
  per-service directories and into a single top-level `infra/sam/<service>/`
  tree. Separates all IaC from all application code at the repo root level.
- Structure:
  ```
  infra/sam/
    main-service/
    attachments-service/
    ai-assistant/
  services/
    main-service/src/
    attachments-service/src/
    ai-assistant/src/
  ```
- Implication: `CodeUri` paths in templates shift from `../src` to
  `../../../services/<service>/src`. SAM resolves CodeUri relative to template
  file location.
- CI change: All `working-directory` values updated to `./infra/sam/<service>`.
- Lesson: Centralising IaC under a single top-level `infra/` makes the repo
  layout unambiguous for teams used to Terraform-style monorepos. The only cost
  is deeper relative CodeUri paths.
- Blog relevance: Medium — useful layout pattern for multi-service SAM repos.
- Tags: `sam`, `infrastructure`, `serverless`, `ci`

---

### Decision: Backend pipelines write VITE_* values as GitHub secrets post-deploy

- Date: 2026-04-10
- Related area: CI/CD / secret management
- Trigger: Design decision
- Problem: Frontend Vite build needs API endpoints, Cognito IDs, and the
  WebSocket URL as environment variables at build time. Manually maintaining
  these secrets after every backend change is error-prone.
- Decision: Each backend pipeline adds a post-deploy step that calls
  `aws cloudformation describe-stacks`, extracts outputs, and writes them as
  GitHub secrets via `gh secret set` using a `GH_PAT` token.
- Secret propagation map:
  - `main-service` → `VITE_TODO_API_ENDPOINT`, `VITE_COGNITO_USER_POOL_ID`,
    `VITE_COGNITO_CLIENT_ID`, `COGNITO_USER_POOL_ID`
  - `attachments-service` → `VITE_FILES_API_ENDPOINT`,
    `VITE_COGNITO_IDENTITY_POOL_ID`, `VITE_S3_BUCKET`, `VITE_AWS_REGION`
  - `ai-assistant` → `VITE_CHATBOT_WS_ENDPOINT`
- Requirement: `GH_PAT` fine-grained token with `secrets:write` scoped to this
  repo. Cannot use default `GITHUB_TOKEN` — it does not support secrets write.
- Deploy order constraint: `main-service` must run before `ai-assistant`
  because it creates `COGNITO_USER_POOL_ID` which the ai-assistant pipeline
  needs as a parameter override.
- Blog relevance: High — automated secret propagation from CFN outputs is a
  common gap in beginner CI/CD setups.
- Tags: `ci`, `github-actions`, `secrets`, `cloudformation`

---

### Gotcha: Pipeline path triggers don't fire on workflow file changes alone

- Date: 2026-04-10
- Related area: CI/CD / GitHub Actions
- Trigger: Gotcha — only frontend pipeline ran after merge
- Observation: After merging the branch that overhauled all four pipelines, only
  the frontend pipeline fired. The three backend pipelines were silent.
- Root cause: GitHub Actions path filters evaluate against files changed in the
  push. The merge changed only workflow files and `infra/sam/` — no files under
  `services/main-service/**`, `services/attachments-service/**`, or
  `services/ai-assistant/**` were modified in that diff.
- Fix: Added `workflow_dispatch` trigger to all three backend pipelines, and
  also added `infra/sam/<service>/**` as a second path filter so template
  changes trigger the right pipeline going forward.
- Lesson: When restructuring pipelines or moving templates, expect that the
  pipelines won't auto-trigger on merge unless source files also change. Always
  add `workflow_dispatch` to SAM pipelines for manual re-runs.
- Blog relevance: Medium — catches people off guard on first CI setup.
- Tags: `ci`, `github-actions`, `sam`

---

### Gotcha: Python 3.8 runtime fails on Ubuntu 24.04 runners

- Date: 2026-04-10
- Related area: CI/CD / Lambda runtime
- Trigger: Pipeline failure
- Error: `PythonPipBuilder:Validation - Binary validation failed for python ...
  did not satisfy constraints for runtime: python3.8`
- Root cause: Ubuntu 24.04 GitHub Actions runners do not ship Python 3.8.
  Python 3.8 reached end of life in October 2024 and was dropped from the
  runner image.
- Fix: Upgraded `Runtime: python3.8` → `Runtime: python3.12` in both
  `infra/sam/main-service/template.yaml` and
  `infra/sam/attachments-service/template.yaml`. All Lambda handlers use only
  stdlib and boto3 — no compatibility changes required.
- Lesson: Python 3.8 is EOL. Any SAM project that hasn't been touched since
  2023 will fail this validation on a current runner. Upgrade runtime first,
  not last.
- Blog relevance: Low — routine maintenance, but worth a callout in any
  "migrate your old SAM project" post.
- Tags: `lambda`, `python`, `sam`, `ci`, `runtime`

---

### Decision: Replace third-party deploy actions with direct AWS CLI calls

- Date: 2026-04-10
- Related area: CI/CD / frontend deployment
- Trigger: Best practice / security
- Decision: Replaced `jakejarvis/s3-sync-action@master` and
  `chetan/invalidate-cloudfront-action@master` with direct AWS CLI commands
  (`aws s3 sync` and `aws cloudfront create-invalidation`).
- Why: Pinning third-party actions to `@master` is a supply chain risk — any
  push to that branch runs untrusted code in your pipeline. The AWS CLI is
  pre-installed on all ubuntu-latest runners; there is no benefit to the
  abstraction.
- Lesson: For simple AWS CLI operations, prefer the CLI directly over
  third-party wrapper actions. Reserve third-party actions for complex
  integrations where the abstraction has real value.
- Blog relevance: Medium — supply chain security is increasingly relevant.
- Tags: `ci`, `github-actions`, `security`, `s3`, `cloudfront`

---

---

## Phase 2 — AI Full Capabilities + Attachment Fix (2026-04-11)

**Goal:** Full CRUD for todos via AI, attachment management via AI, fix frontend upload flow, drag-and-drop to chat.

### Architecture decisions

**Decision: addTodoFile takes CDN URL, not S3 key**
- The Bedrock Agent receives a CDN URL from the frontend (after S3 upload). The agent calls `addTodoFile(todoID, fileName, fileUrl)` with the full URL. This means the agent never touches S3 presigned URLs — simpler action schema, safer boundary.
- Blog relevance: Medium — good illustration of clean AI/backend interface design.

**Decision: S3 key extraction via URL stripping for delete operations**
- `deleteTodo` and `deleteTodoFile` strip the CDN domain prefix and URL-decode to get the S3 key. Initial implementation only decoded `%40` (@) — a code review caught this. Fixed with `urllib.parse.unquote`.
- Lesson: Any S3 key derivation from a CDN URL must use proper URL decoding, not character-by-character replacement.
- Blog relevance: Medium — practical gotcha for S3 + CloudFront setups.

**Decision: initChatDropZone guards against double-registration**
- Added `drawer.dataset.dropzoneInit` guard so opening the chat panel multiple times doesn't stack multiple drop listeners. A subtle bug that's easy to miss with event delegation.

### Bugs fixed during implementation

**Bug: Duplicate boto3 DynamoDB client**
- Code review caught that `files_client` was an identical duplicate of `client`. Both were DynamoDB clients with the same region config. Removed — boto3 clients are stateless with respect to the table they target.
- Blog relevance: Low — routine, but illustrates value of code review on generated code.

**Bug: Wrong import in delete file handler (home.ts)**
- `renderFiles` was being imported from `../api` instead of `../ui`. TypeScript caught this at build time (`Property 'renderFiles' does not exist on type 'typeof import("...api")'`).

### CI/CD fix: main-service pipeline region mismatch

**Symptom:** `UPDATE_ROLLBACK_COMPLETE` on `todo-houessou-com` stack in `us-east-1`. Lambda functions failing with `AuthorizationHeaderMalformed: region '***' is wrong; expecting 'ca-central-1'`.

**Root cause:** The SAM deploy used an explicit `--s3-bucket` pointing to a `ca-central-1` bucket, while `--region ${{ secrets.AWS_REGION }}` was `us-east-1`. CloudFormation fetched Lambda code from the ca-central-1 bucket using us-east-1 signing — S3 rejected it.

**Fix:** Added `--resolve-s3` to the deploy command (SAM auto-creates a managed bucket in the target region) and updated `samconfig.toml` region from `ca-central-1` to `us-east-1` to match reality.

**Key insight:** `--resolve-s3` eliminates the coupling between `samconfig.toml` S3 bucket config and the deploy region. It's the correct default for multi-region or team setups where the SAM bucket location may not match the deployment region.

- Blog relevance: High — this exact error pattern (SAM + wrong S3 region) is a frequent CI/CD gotcha.
- Tags: `sam`, `s3`, `ci`, `cloudformation`, `serverless`

---

## Strongest blog candidates so far

1. WebSocket + Bedrock: the session persistence bug everyone makes
2. WebSocket $connect auth: why query string, not headers
3. Single-table DynamoDB for WebSocket connection + session tracking
4. Bedrock model invocation logging: the operational blind spot
5. Automated secret propagation: writing CFN outputs to GitHub secrets in CI
6. CI/CD supply chain: replacing `@master` third-party actions with AWS CLI