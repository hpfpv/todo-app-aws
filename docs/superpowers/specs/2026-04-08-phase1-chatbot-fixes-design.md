# Phase 1: Chatbot Production Fixes — Design Spec

- **Date:** 2026-04-08
- **Branch:** chatbot
- **Status:** Approved

## 1. Goal

Bring the Bedrock chatbot Lambda code into the repository as a proper SAM service,
fix the critical session persistence bug, add WebSocket auth, make trace configurable,
upgrade to Amazon Nova Micro, add Bedrock observability, and fix the frontend WebSocket
lifecycle. The existing Bedrock Agent (VLLFJVDUBD) and its action group definition are
kept as-is; only the Lambda code and infrastructure are changing.

## 2. Scope

### In scope

- Create `services/ai-assistant/` SAM service with full IaC
- Fix session persistence (stable `sessionId` per userID, survives reconnects)
- Add Lambda authorizer on `$connect` for Cognito JWT validation
- Remove `userID` from frontend payload (read from JWT context instead)
- Fix frontend: single persistent WebSocket per chat session
- Upgrade Bedrock Agent model to Amazon Nova Micro (`amazon.nova-micro-v1:0`)
- Add X-Ray tracing, structured JSON logs, Bedrock model invocation logging
- Scope IAM to least-privilege per function

### Out of scope

- Bedrock native Memory (Phase 2)
- Bedrock Guardrails (Phase 2)
- Knowledge Base / RAG (Phase 2+)
- AgentCore migration (Phase 3)
- Unit test suite with pytest (Phase 2)
- CI/CD pipeline for ai-assistant service

## 3. Architecture

```
Browser (Vite/TS)
  │  open WS on chat panel open
  │  wss://<endpoint>?token=<CognitoIdToken>
  ▼
API Gateway WebSocket
  │
  ├── $connect ──▶ Lambda Authorizer
  │                 validates Cognito JWT (JWKS)
  │                 passes userID via authorizer context
  │
  ├── $connect (authorized) ──▶ WebSocketHandler
  │   $disconnect             lookup/create sessionId in BotTable
  │   $default                invoke Bedrock Agent, post response back
  │
  └── Action Group invocation ──▶ ActionGroupHandler
                                   todos CRUD via DynamoDB TodoTable
```

**BotTable dual-key design (single table, two item types):**

```
PK=<connectionId>  →  { userID, sessionId, ttl }   # deleted on $disconnect
PK=<userID>        →  { sessionId, ttl }            # survives reconnects (30 min TTL)
```

Session reuse logic on `$connect`:

1. Read `PK=userID` item
2. If found and `ttl > now`: reuse `sessionId`
3. Otherwise: generate new `uuid4`, write/overwrite both items
4. Write `PK=connectionId` item with same `sessionId`

## 4. Repository Structure

```
services/ai-assistant/
├── template.yaml
├── samconfig.toml
├── src/
│   ├── authorizer/
│   │   ├── handler.py
│   │   └── requirements.txt       # PyJWT, cryptography
│   ├── websocket_handler/
│   │   ├── handler.py
│   │   └── requirements.txt       # boto3 (runtime provided)
│   └── action_group/
│       ├── handler.py             # existing code, cleaned up
│       └── requirements.txt       # boto3 (runtime provided)
└── events/
    ├── connect.json
    ├── disconnect.json
    ├── message.json
    └── action_group.json
```

## 5. SAM Resources (`template.yaml`)

| Resource | Type | Notes |
|---|---|---|
| `ChatbotWebSocketApi` | `AWS::ApiGatewayV2::Api` | WebSocket, routes: $connect/$disconnect/$default |
| `AuthorizerFunction` | `AWS::Serverless::Function` | Python 3.12, Lambda authorizer on $connect |
| `WebSocketHandlerFunction` | `AWS::Serverless::Function` | Python 3.12, all three routes |
| `ActionGroupHandlerFunction` | `AWS::Serverless::Function` | Python 3.12, Bedrock action group target |
| `EnableBedrockLoggingFunction` | `AWS::Serverless::Function` | Custom Resource, one-shot setup |
| `BotTable` | `AWS::DynamoDB::Table` | PAY_PER_REQUEST, TTL on `ttl` attribute |
| `BedrockInvocationLogGroup` | `AWS::Logs::LogGroup` | `/aws/bedrock/model-invocations`, 7-day retention |
| `BedrockLoggingRole` | `AWS::IAM::Role` | Assumed by Bedrock to write invocation logs |
| `BedrockLoggingCustomResource` | `AWS::CloudFormation::CustomResource` | Triggers EnableBedrockLoggingFunction |

**Python runtime:** `python3.12` (upgraded from main-service's `python3.8`)

## 6. Environment Variables

### `WebSocketHandlerFunction`

| Variable | Value |
|---|---|
| `BOT_TABLE` | `!Ref BotTable` |
| `AGENT_ID` | `VLLFJVDUBD` |
| `AGENT_ALIAS_ID` | `JLCNDHYLCT` |
| `ENABLE_TRACE` | `false` (set `true` for debugging only) |
| `WS_ENDPOINT` | WebSocket management endpoint |

### `ActionGroupHandlerFunction`

| Variable | Value |
|---|---|
| `TODO_TABLE` | `!ImportValue todo-houessou-com-main-service-TodoTable` |

### `AuthorizerFunction`

| Variable | Value |
|---|---|
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID |
| `COGNITO_REGION` | `us-east-1` |

## 7. Lambda Function Designs

### `authorizer/handler.py`

- Receives `$connect` event with `queryStringParameters.token`
- Fetches Cognito JWKS from `https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/jwks.json`
- JWKS response cached in module scope between warm invocations
- Validates: signature, expiry, `aud` matches Cognito Client ID
- Returns IAM policy: `Allow` or `Deny` on `execute-api:Invoke`
- Passes `userID` (from JWT `email` claim) as authorizer context

### `websocket_handler/handler.py`

**`$connect`:**

1. Get `userID` from `event['requestContext']['authorizer']['userID']`
2. Get `connectionId` from `event['requestContext']['connectionId']`
3. `get_item(PK=userID)` from BotTable
4. If item exists and `ttl > int(time.time())`: use existing `sessionId`
5. Else: `sessionId = str(uuid.uuid4())`
6. `put_item(PK=connectionId, userID=userID, sessionId=sessionId, ttl=now+1800)`
7. `put_item(PK=userID, sessionId=sessionId, ttl=now+1800)`
8. Return `{'statusCode': 200}`

**`$disconnect`:**

1. Get `connectionId`
2. `delete_item(PK=connectionId)`
3. Return `{'statusCode': 200}`

**`$default`:**

1. Get `connectionId`, `userID` from authorizer context
2. Get `sessionId` from `get_item(PK=connectionId).sessionId`
3. If missing: generate new `sessionId`, write both items (recovery path)
4. Parse `body` → `human`
5. `inputText = f"<userid>{userID}</userid>\n{human}"`
6. `invoke_agent(agentId, agentAliasId, sessionId, inputText, enableTrace)`
7. Stream event_stream, collect final `chunk` bytes → `agent_answer`
8. `post_to_connection(connectionId, json.dumps({'response': agent_answer}))`
9. Log structured JSON: `connectionId`, `userID[:3]***`, `sessionId`, `inputLength`, `responseLength`
10. Return `{'statusCode': 200}`

**Error handling:**
- Bedrock timeout / exception → post `{'response': 'Sorry, something went wrong. Please try again.'}` then re-raise
- `GoneException` on post-back → log and swallow (client already disconnected)
- Missing `sessionId` on `$default` → recovery path (step 3 above)

### `action_group/handler.py`

Existing logic preserved. Changes:
- Remove unused imports: `zipfile`, `BytesIO`, `random`, `time`, `pprint`
- Structured JSON logging replacing raw `print`
- No behaviour changes

## 8. Frontend Changes (`apps/web/src/chatbot.ts`)

```typescript
// Module-level WebSocket instance
let ws: WebSocket | null = null;

export function openChatSession(): void {
  const tokens = JSON.parse(localStorage.getItem('sessionTokens') ?? '{}');
  const token = tokens?.IdToken?.jwtToken;
  if (!token) { /* redirect to login */ return; }
  ws = new WebSocket(`${config.chatbotWsEndpoint}?token=${token}`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    removeTypingIndicator();
    displayMessage(data.response, 'bot');
  };
  ws.onerror = () => {
    removeTypingIndicator();
    displayMessage('Connection error. Please try again.', 'bot');
  };
  ws.onclose = () => { ws = null; };
}

export function closeChatSession(): void {
  if (ws?.readyState === WebSocket.OPEN) ws.close();
  ws = null;
}

export function sendMessage(): void {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    displayMessage('Not connected. Please refresh.', 'bot');
    return;
  }
  const userInput = document.getElementById('userInput') as HTMLInputElement;
  const message = userInput.value.trim();
  if (!message) return;
  userInput.value = '';
  displayMessage(message, 'user');
  displayTypingIndicator();
  ws.send(JSON.stringify({ human: message }));  // no userID in payload
}
```

`home.ts` calls `openChatSession()` on panel show, `closeChatSession()` on panel hide
and `window.addEventListener('beforeunload', closeChatSession)`.

## 9. IAM Scoping

### `WebSocketHandlerFunction`

```yaml
- dynamodb:GetItem, PutItem, DeleteItem  # BotTable only
- bedrock:InvokeAgent                    # scoped to agent ARN
- execute-api:ManageConnections          # WebSocket stage ARN
```

### `ActionGroupHandlerFunction`

```yaml
- dynamodb:GetItem, Query, PutItem, UpdateItem  # TodoTable + GSI ARN
```

### `AuthorizerFunction`

No AWS API permissions. HTTPS to Cognito JWKS only.

## 10. Observability

### X-Ray

`Tracing: Active` on all Lambda functions in SAM Globals.

### Structured Logging

All Lambda functions emit JSON log lines. Format:

```json
{
  "level": "INFO",
  "route": "$default",
  "connectionId": "abc123",
  "userIdPrefix": "hpf***",
  "sessionId": "uuid",
  "inputLength": 42,
  "responseLength": 180,
  "agentDurationMs": 1240
}
```

### Bedrock Model Invocation Logging

- `BedrockInvocationLogGroup`: `/aws/bedrock/model-invocations`, 7-day retention
- `BedrockLoggingRole`: allows `bedrock.amazonaws.com` to `logs:CreateLogStream`, `logs:PutLogEvents`
- `EnableBedrockLoggingFunction`: Custom Resource Lambda that calls
  `bedrock.put_model_invocation_logging_configuration()` on stack create/update
- Captures: model ID, prompt summary, token counts, latency per invocation

## 11. Model

**Bedrock Agent model:** `amazon.nova-micro-v1:0` (Amazon Nova Micro)

- Cheapest Nova model
- Supports tool use (required for action groups)
- Text-only input/output — fits this use case exactly
- Change made in Bedrock Agent console configuration, not in Lambda code

## 12. Testing

Local testing via `sam local invoke` using event files in `events/`:

```bash
sam local invoke AuthorizerFunction -e events/connect.json
sam local invoke WebSocketHandlerFunction -e events/connect.json
sam local invoke WebSocketHandlerFunction -e events/message.json
sam local invoke WebSocketHandlerFunction -e events/disconnect.json
sam local invoke ActionGroupHandlerFunction -e events/action_group.json
```

No pytest suite in Phase 1. Unit tests added in Phase 2.

## 13. Implementation Log

Per `implementation-content-logging-steering-standard-v1.0.md`, a running log will
be maintained at `docs/content/implementation-log.md` throughout Phase 1.

## 14. Open Questions / Notes

- Bedrock Agent model change (`amazon.nova-micro-v1:0`) requires re-preparing the agent
  in the console after update. This is a manual step noted in the implementation plan.
- `ENABLE_TRACE=true` should only be set in dev. Trace output significantly increases
  CloudWatch log volume and agent response latency.
- WebSocket API GW has a 10-minute idle connection timeout. The frontend chat panel
  is expected to be used interactively so this is acceptable in Phase 1.
- Cognito token expiry (typically 1 hour): if the token expires while the WebSocket
  is open, the existing connection stays alive (auth only checked at `$connect`).
  Token refresh on reconnect handles this gracefully.
