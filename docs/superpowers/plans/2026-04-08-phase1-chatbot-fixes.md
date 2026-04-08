# Phase 1: Chatbot Production Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Bedrock chatbot into IaC as a SAM service, fix session persistence,
add WebSocket auth, add observability, upgrade to Nova Micro, and fix the frontend
WebSocket lifecycle.

**Architecture:** Lambda authorizer validates Cognito JWT on `$connect`. WebSocket
handler manages a dual-key DynamoDB table (BotTable) to persist `sessionId` per `userID`
across reconnects. Frontend opens one WebSocket per chat session instead of one per
message.

**Tech Stack:** Python 3.12, AWS SAM, API Gateway WebSocket V2, DynamoDB, Bedrock
Agent Runtime, PyJWT, TypeScript + Vite

---

## File Map

### Created

```
services/ai-assistant/
├── template.yaml
├── samconfig.toml
├── src/
│   ├── authorizer/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── websocket_handler/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── action_group/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── enable_bedrock_logging/
│       ├── handler.py
│       └── requirements.txt
└── events/
    ├── connect.json
    ├── disconnect.json
    ├── message.json
    └── action_group.json
```

### Modified

```
apps/web/src/chatbot.ts           — persistent WebSocket lifecycle
apps/web/src/pages/home.ts        — openChatSession / closeChatSession hooks
```

---

## Task 1: Scaffold service directories

**Files:**
- Create: `services/ai-assistant/src/authorizer/`
- Create: `services/ai-assistant/src/websocket_handler/`
- Create: `services/ai-assistant/src/action_group/`
- Create: `services/ai-assistant/src/enable_bedrock_logging/`
- Create: `services/ai-assistant/events/`

- [ ] **Step 1: Create directories and placeholder files**

```bash
mkdir -p services/ai-assistant/src/authorizer
mkdir -p services/ai-assistant/src/websocket_handler
mkdir -p services/ai-assistant/src/action_group
mkdir -p services/ai-assistant/src/enable_bedrock_logging
mkdir -p services/ai-assistant/events
touch services/ai-assistant/src/authorizer/__init__.py
touch services/ai-assistant/src/websocket_handler/__init__.py
touch services/ai-assistant/src/action_group/__init__.py
touch services/ai-assistant/src/enable_bedrock_logging/__init__.py
```

- [ ] **Step 2: Create empty requirements.txt files**

```bash
touch services/ai-assistant/src/websocket_handler/requirements.txt
touch services/ai-assistant/src/action_group/requirements.txt
touch services/ai-assistant/src/enable_bedrock_logging/requirements.txt
```

`services/ai-assistant/src/authorizer/requirements.txt`:

```
PyJWT[crypto]==2.10.1
```

- [ ] **Step 3: Commit scaffold**

```bash
git add services/ai-assistant/
git commit -m "chore(ai-assistant): scaffold service directory structure"
```

---

## Task 2: Action group Lambda

Bring the existing action group code into the repo, cleaned up.

**Files:**
- Create: `services/ai-assistant/src/action_group/handler.py`
- Create: `services/ai-assistant/events/action_group.json`

- [ ] **Step 1: Write test event**

`services/ai-assistant/events/action_group.json`:

```json
{
  "actionGroup": "todos",
  "apiPath": "/{userID}/todos",
  "httpMethod": "GET",
  "parameters": [
    { "name": "userID", "type": "string", "value": "test@example.com" }
  ],
  "requestBody": {}
}
```

- [ ] **Step 2: Write handler**

`services/ai-assistant/src/action_group/handler.py`:

```python
import boto3
import json
import logging
import os
import uuid
from datetime import datetime

client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _todo_from_item(item):
    return {
        'todoID': item['todoID']['S'],
        'userID': item['userID']['S'],
        'dateCreated': item['dateCreated']['S'],
        'title': item['title']['S'],
        'description': item['description']['S'],
        'notes': item['notes']['S'],
        'dateDue': item['dateDue']['S'],
        'completed': item['completed']['BOOL'],
    }


def getTodo(todoID):
    response = client.get_item(
        TableName=os.environ['TODO_TABLE'],
        Key={'todoID': {'S': todoID}}
    )
    return _todo_from_item(response['Item'])


def getTodos(userID):
    response = client.query(
        TableName=os.environ['TODO_TABLE'],
        IndexName='userIDIndex',
        KeyConditions={
            'userID': {
                'AttributeValueList': [{'S': userID}],
                'ComparisonOperator': 'EQ'
            }
        }
    )
    todos = [_todo_from_item(item) for item in response['Items']]
    todos = sorted(todos, key=lambda i: i['dateCreated'], reverse=True)
    todos = sorted(todos, key=lambda i: i['dateDue'])
    todos = sorted(todos, key=lambda i: i['completed'])
    logger.info(json.dumps({'action': 'getTodos', 'userID': userID[:3] + '***', 'count': len(todos)}))
    return {'todos': todos}


def addTodo(userID, body):
    now = datetime.now()
    item = {
        'todoID': {'S': str(uuid.uuid4())},
        'userID': {'S': userID},
        'dateCreated': {'S': str(now)},
        'title': {'S': body['title']},
        'description': {'S': body['description']},
        'notes': {'S': ''},
        'dateDue': {'S': body['dateDue']},
        'completed': {'BOOL': False},
    }
    client.put_item(TableName=os.environ['TODO_TABLE'], Item=item)
    logger.info(json.dumps({'action': 'addTodo', 'userID': userID[:3] + '***'}))
    return json.dumps({'status': 'success'})


def addTodoNotes(todoID, notes):
    client.update_item(
        TableName=os.environ['TODO_TABLE'],
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET notes = :n',
        ExpressionAttributeValues={':n': {'S': notes}}
    )
    logger.info(json.dumps({'action': 'addTodoNotes', 'todoID': todoID}))
    return json.dumps({'Update': 'Success'})


def completeTodo(todoID):
    client.update_item(
        TableName=os.environ['TODO_TABLE'],
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET completed = :b',
        ExpressionAttributeValues={':b': {'BOOL': True}}
    )
    logger.info(json.dumps({'action': 'completeTodo', 'todoID': todoID}))
    return json.dumps({'Update': 'Success'})


def lambda_handler(event, context):
    logger.info(json.dumps({'event': event}))
    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    api_path = event['apiPath']

    if api_path == '/{userID}/todos':
        body = getTodos(parameters['userID'])
    elif api_path == '/{userID}/todos/{todoID}':
        body = getTodo(parameters['todoID'])
    elif api_path == '/{userID}/todos/add':
        props = {
            p['name']: p['value']
            for p in event['requestBody']['content']['application/json']['properties']
        }
        body = addTodo(parameters['userID'], props)
    elif api_path == '/{userID}/todos/{todoID}/addnotes':
        props = {
            p['name']: p['value']
            for p in event['requestBody']['content']['application/json']['properties']
        }
        body = addTodoNotes(parameters['todoID'], props['notes'])
    elif api_path == '/{userID}/todos/{todoID}/complete':
        body = completeTodo(parameters['todoID'])
    else:
        body = {'error': f'{event["actionGroup"]}::{api_path} is not a valid api path'}

    return {
        'response': {
            'actionGroup': event['actionGroup'],
            'apiPath': event['apiPath'],
            'httpMethod': event['httpMethod'],
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {'body': str(body)}
            }
        }
    }
```

- [ ] **Step 3: Test locally (requires TODO_TABLE env var — skip if no local DynamoDB)**

```bash
cd services/ai-assistant
TODO_TABLE=TodoTable-todo-houessou-com \
sam local invoke ActionGroupHandlerFunction \
  -e events/action_group.json \
  --env-vars <(echo '{"ActionGroupHandlerFunction":{"TODO_TABLE":"TodoTable-todo-houessou-com"}}') \
  2>&1 | tail -20
```

Expected: JSON response with `httpStatusCode: 200`. A DynamoDB error is acceptable
here since no local DB is running — the important check is that the Lambda
initializes correctly (no import errors).

- [ ] **Step 4: Commit**

```bash
git add services/ai-assistant/src/action_group/ services/ai-assistant/events/action_group.json
git commit -m "feat(ai-assistant): add action group Lambda with structured logging"
```

---

## Task 3: Lambda Authorizer

Validates Cognito JWT from `?token=` query string on `$connect`.

**Files:**
- Create: `services/ai-assistant/src/authorizer/handler.py`
- Create: `services/ai-assistant/events/connect.json`

- [ ] **Step 1: Write test event**

`services/ai-assistant/events/connect.json`:

```json
{
  "type": "REQUEST",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef1234/production/$connect",
  "queryStringParameters": {
    "token": "REPLACE_WITH_VALID_COGNITO_ID_TOKEN"
  },
  "requestContext": {
    "routeKey": "$connect",
    "connectionId": "test-connection-id"
  }
}
```

- [ ] **Step 2: Write handler**

`services/ai-assistant/src/authorizer/handler.py`:

```python
import json
import os
import time
import urllib.request
import logging
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_JWKS_CACHE = None
_JWKS_CACHE_TIME = 0
_JWKS_TTL = 3600  # seconds


def _get_jwks():
    global _JWKS_CACHE, _JWKS_CACHE_TIME
    now = time.time()
    if _JWKS_CACHE and (now - _JWKS_CACHE_TIME) < _JWKS_TTL:
        return _JWKS_CACHE
    pool_id = os.environ['COGNITO_USER_POOL_ID']
    region = os.environ['COGNITO_REGION']
    url = (
        f'https://cognito-idp.{region}.amazonaws.com'
        f'/{pool_id}/.well-known/jwks.json'
    )
    with urllib.request.urlopen(url, timeout=5) as resp:
        _JWKS_CACHE = json.loads(resp.read())
    _JWKS_CACHE_TIME = now
    return _JWKS_CACHE


def _get_public_key(kid):
    jwks = _get_jwks()
    for key in jwks['keys']:
        if key['kid'] == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))
    raise ValueError(f'Key {kid} not found in JWKS')


def _policy(principal_id, effect, resource, context=None):
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource,
            }],
        },
    }
    if context:
        policy['context'] = context
    return policy


def lambda_handler(event, context):
    method_arn = event['methodArn']
    token = (event.get('queryStringParameters') or {}).get('token')

    if not token:
        logger.info(json.dumps({'level': 'INFO', 'result': 'Deny', 'reason': 'no token'}))
        return _policy('anonymous', 'Deny', method_arn)

    try:
        header = jwt.get_unverified_header(token)
        public_key = _get_public_key(header['kid'])
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={'verify_aud': False},
        )
        user_id = payload.get('email') or payload.get('cognito:username', 'unknown')
        logger.info(json.dumps({
            'level': 'INFO',
            'result': 'Allow',
            'userIdPrefix': user_id[:3] + '***',
        }))
        return _policy(user_id, 'Allow', method_arn, {'userID': user_id})
    except Exception as exc:
        logger.error(json.dumps({'level': 'ERROR', 'result': 'Deny', 'reason': str(exc)}))
        return _policy('anonymous', 'Deny', method_arn)
```

- [ ] **Step 3: Test with a valid token (get one from localStorage after logging in)**

```bash
cd services/ai-assistant
COGNITO_USER_POOL_ID=<your-pool-id> \
COGNITO_REGION=us-east-1 \
sam local invoke AuthorizerFunction \
  -e events/connect.json \
  --env-vars <(echo '{
    "AuthorizerFunction": {
      "COGNITO_USER_POOL_ID": "<your-pool-id>",
      "COGNITO_REGION": "us-east-1"
    }
  }') \
  2>&1 | tail -20
```

Expected output with a valid token:

```json
{"principalId": "user@example.com", "policyDocument": {...}, "context": {"userID": "user@example.com"}}
```

Expected output with `"token": "invalid"`:

```json
{"principalId": "anonymous", "policyDocument": {"Statement": [{"Effect": "Deny", ...}]}}
```

- [ ] **Step 4: Commit**

```bash
git add services/ai-assistant/src/authorizer/ services/ai-assistant/events/connect.json
git commit -m "feat(ai-assistant): add Cognito JWT Lambda authorizer for WebSocket \$connect"
```

---

## Task 4: WebSocket Handler — connect and disconnect

**Files:**
- Create: `services/ai-assistant/src/websocket_handler/handler.py` (connect + disconnect only)
- Create: `services/ai-assistant/events/disconnect.json`

- [ ] **Step 1: Write disconnect test event**

`services/ai-assistant/events/disconnect.json`:

```json
{
  "requestContext": {
    "routeKey": "$disconnect",
    "connectionId": "test-connection-id-abc123",
    "disconnectStatusCode": 1001
  }
}
```

- [ ] **Step 2: Write handler (connect + disconnect, no Bedrock yet)**

`services/ai-assistant/src/websocket_handler/handler.py`:

```python
import boto3
import json
import logging
import os
import time
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
BOT_TABLE = os.environ.get('BOT_TABLE', '')
SESSION_TTL_SECONDS = 1800  # 30 minutes — matches Bedrock session idle timeout


def _connect(connection_id, user_id):
    now = int(time.time())
    # Check for an existing session for this user
    response = dynamodb.get_item(
        TableName=BOT_TABLE,
        Key={'pk': {'S': user_id}},
    )
    item = response.get('Item')
    if item and int(item['ttl']['N']) > now:
        session_id = item['sessionId']['S']
        logger.info(json.dumps({
            'level': 'INFO', 'route': '$connect', 'action': 'reuse_session',
            'connectionId': connection_id, 'userIdPrefix': user_id[:3] + '***',
        }))
    else:
        session_id = str(uuid.uuid4())
        logger.info(json.dumps({
            'level': 'INFO', 'route': '$connect', 'action': 'new_session',
            'connectionId': connection_id, 'userIdPrefix': user_id[:3] + '***',
        }))

    ttl = now + SESSION_TTL_SECONDS
    # Write connection item (deleted on disconnect)
    dynamodb.put_item(
        TableName=BOT_TABLE,
        Item={
            'pk': {'S': connection_id},
            'userID': {'S': user_id},
            'sessionId': {'S': session_id},
            'ttl': {'N': str(ttl)},
        },
    )
    # Write/refresh user session item (survives disconnect)
    dynamodb.put_item(
        TableName=BOT_TABLE,
        Item={
            'pk': {'S': user_id},
            'sessionId': {'S': session_id},
            'ttl': {'N': str(ttl)},
        },
    )
    return {'statusCode': 200}


def _disconnect(connection_id):
    dynamodb.delete_item(
        TableName=BOT_TABLE,
        Key={'pk': {'S': connection_id}},
    )
    logger.info(json.dumps({
        'level': 'INFO', 'route': '$disconnect',
        'connectionId': connection_id,
    }))
    return {'statusCode': 200}


def _default(connection_id, user_id, body_str):
    # Bedrock invocation added in Task 5
    return {'statusCode': 501, 'body': 'Not implemented yet'}


def lambda_handler(event, context):
    route = event['requestContext']['routeKey']
    connection_id = event['requestContext']['connectionId']

    if route == '$connect':
        user_id = event['requestContext'].get('authorizer', {}).get('userID', 'unknown')
        return _connect(connection_id, user_id)
    elif route == '$disconnect':
        return _disconnect(connection_id)
    else:
        user_id = event['requestContext'].get('authorizer', {}).get('userID', 'unknown')
        body_str = event.get('body', '{}')
        return _default(connection_id, user_id, body_str)
```

- [ ] **Step 3: Test disconnect handler locally**

```bash
cd services/ai-assistant
sam local invoke WebSocketHandlerFunction \
  -e events/disconnect.json \
  --env-vars <(echo '{
    "WebSocketHandlerFunction": {
      "BOT_TABLE": "BotTable-test",
      "AGENT_ID": "VLLFJVDUBD",
      "AGENT_ALIAS_ID": "JLCNDHYLCT",
      "ENABLE_TRACE": "false",
      "WS_ENDPOINT": "https://placeholder.execute-api.us-east-1.amazonaws.com/production"
    }
  }') \
  2>&1 | tail -20
```

Expected: A DynamoDB error (no local table) — the important check is that the
Lambda initializes without import errors and routes to `_disconnect`.

- [ ] **Step 4: Commit**

```bash
git add services/ai-assistant/src/websocket_handler/ services/ai-assistant/events/disconnect.json
git commit -m "feat(ai-assistant): add WebSocket handler connect/disconnect with dual-key session management"
```

---

## Task 5: WebSocket Handler — default (Bedrock invocation)

**Files:**
- Modify: `services/ai-assistant/src/websocket_handler/handler.py` — add `_default`
- Create: `services/ai-assistant/events/message.json`

- [ ] **Step 1: Write message test event**

`services/ai-assistant/events/message.json`:

```json
{
  "requestContext": {
    "routeKey": "$default",
    "connectionId": "test-connection-id-abc123",
    "authorizer": {
      "userID": "test@example.com"
    }
  },
  "body": "{\"human\": \"show me my todos\"}"
}
```

- [ ] **Step 2: Add imports and Bedrock clients at top of handler**

Replace the top section of `services/ai-assistant/src/websocket_handler/handler.py`
(everything above `BOT_TABLE = ...`) with:

```python
import boto3
import json
import logging
import os
import time
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

BOT_TABLE = os.environ.get('BOT_TABLE', '')
AGENT_ID = os.environ.get('AGENT_ID', '')
AGENT_ALIAS_ID = os.environ.get('AGENT_ALIAS_ID', '')
ENABLE_TRACE = os.environ.get('ENABLE_TRACE', 'false').lower() == 'true'
SESSION_TTL_SECONDS = 1800
```

- [ ] **Step 3: Replace the `_default` stub with the full implementation**

Replace the `_default` function in `services/ai-assistant/src/websocket_handler/handler.py`:

```python
def _default(connection_id, user_id, body_str):
    start = time.time()
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        body = {}
    human = body.get('human', '').strip()
    if not human:
        return {'statusCode': 400}

    # Get sessionId for this connection
    response = dynamodb.get_item(
        TableName=BOT_TABLE,
        Key={'pk': {'S': connection_id}},
    )
    conn_item = response.get('Item')
    if conn_item:
        session_id = conn_item['sessionId']['S']
    else:
        # Recovery: connection item missing, create new session
        session_id = str(uuid.uuid4())
        ttl = int(time.time()) + SESSION_TTL_SECONDS
        dynamodb.put_item(
            TableName=BOT_TABLE,
            Item={
                'pk': {'S': connection_id},
                'userID': {'S': user_id},
                'sessionId': {'S': session_id},
                'ttl': {'N': str(ttl)},
            },
        )
        dynamodb.put_item(
            TableName=BOT_TABLE,
            Item={
                'pk': {'S': user_id},
                'sessionId': {'S': session_id},
                'ttl': {'N': str(ttl)},
            },
        )
        logger.info(json.dumps({
            'level': 'WARN', 'route': '$default',
            'action': 'session_recovery', 'connectionId': connection_id,
        }))

    input_text = f'<userid>{user_id}</userid>\n{human}'

    # Invoke Bedrock Agent
    agent_response = bedrock_agent_runtime.invoke_agent(
        inputText=input_text,
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        enableTrace=ENABLE_TRACE,
        endSession=False,
    )

    # Stream the response and collect final answer
    agent_answer = ''
    for event in agent_response['completion']:
        if 'chunk' in event:
            agent_answer = event['chunk']['bytes'].decode('utf-8')
        elif 'trace' in event and ENABLE_TRACE:
            logger.info(json.dumps({'trace': event['trace']}))

    duration_ms = int((time.time() - start) * 1000)
    logger.info(json.dumps({
        'level': 'INFO', 'route': '$default',
        'connectionId': connection_id,
        'userIdPrefix': user_id[:3] + '***',
        'sessionId': session_id,
        'inputLength': len(human),
        'responseLength': len(agent_answer),
        'agentDurationMs': duration_ms,
    }))

    # Post response back to the WebSocket connection
    ws_endpoint = os.environ.get('WS_ENDPOINT', '')
    api_gw_mgmt = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=ws_endpoint,
    )
    try:
        api_gw_mgmt.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({'response': agent_answer}),
        )
    except api_gw_mgmt.exceptions.GoneException:
        logger.info(json.dumps({
            'level': 'INFO', 'action': 'connection_gone',
            'connectionId': connection_id,
        }))

    return {'statusCode': 200}
```

- [ ] **Step 4: Add top-level error handler in `lambda_handler`**

Replace the `else:` branch in `lambda_handler`:

```python
    else:
        user_id = event['requestContext'].get('authorizer', {}).get('userID', 'unknown')
        body_str = event.get('body', '{}')
        try:
            return _default(connection_id, user_id, body_str)
        except Exception as exc:
            logger.error(json.dumps({
                'level': 'ERROR', 'route': '$default',
                'connectionId': connection_id, 'error': str(exc),
            }))
            ws_endpoint = os.environ.get('WS_ENDPOINT', '')
            if ws_endpoint:
                try:
                    boto3.client(
                        'apigatewaymanagementapi',
                        endpoint_url=ws_endpoint,
                    ).post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({'response': 'Sorry, something went wrong. Please try again.'}),
                    )
                except Exception:
                    pass
            raise
```

- [ ] **Step 5: Test locally**

```bash
cd services/ai-assistant
sam local invoke WebSocketHandlerFunction \
  -e events/message.json \
  --env-vars <(echo '{
    "WebSocketHandlerFunction": {
      "BOT_TABLE": "BotTable-test",
      "AGENT_ID": "VLLFJVDUBD",
      "AGENT_ALIAS_ID": "JLCNDHYLCT",
      "ENABLE_TRACE": "false",
      "WS_ENDPOINT": "https://placeholder.execute-api.us-east-1.amazonaws.com/production"
    }
  }') \
  2>&1 | tail -30
```

Expected: A DynamoDB or Bedrock error (no credentials / no local resources).
Verify the Lambda initializes without import errors and routes to `_default`.

- [ ] **Step 6: Commit**

```bash
git add services/ai-assistant/src/websocket_handler/handler.py services/ai-assistant/events/message.json
git commit -m "feat(ai-assistant): add Bedrock agent invocation with session reuse in \$default handler"
```

---

## Task 6: Bedrock observability Custom Resource

One-shot Lambda that enables Bedrock model invocation logging on stack create/update.

**Files:**
- Create: `services/ai-assistant/src/enable_bedrock_logging/handler.py`

- [ ] **Step 1: Write handler**

`services/ai-assistant/src/enable_bedrock_logging/handler.py`:

```python
import json
import logging
import os
import urllib.request

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client('bedrock', region_name='us-east-1')


def _send_cfn_response(event, context, status, data=None):
    body = json.dumps({
        'Status': status,
        'Reason': f'See CloudWatch: {context.log_stream_name}',
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {},
    })
    req = urllib.request.Request(
        url=event['ResponseURL'],
        data=body.encode(),
        method='PUT',
        headers={'Content-Type': ''},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.info(json.dumps({'cfn_response_status': resp.status}))


def lambda_handler(event, context):
    logger.info(json.dumps({'RequestType': event.get('RequestType')}))
    try:
        if event['RequestType'] in ('Create', 'Update'):
            bedrock.put_model_invocation_logging_configuration(
                loggingConfig={
                    'cloudWatchConfig': {
                        'logGroupName': '/aws/bedrock/model-invocations',
                        'roleArn': os.environ['LOGGING_ROLE_ARN'],
                        'largeDataDeliveryS3Config': {},
                    },
                    'textDataDeliveryEnabled': True,
                    'imageDataDeliveryEnabled': False,
                    'embeddingDataDeliveryEnabled': False,
                }
            )
            logger.info(json.dumps({'level': 'INFO', 'action': 'bedrock_logging_enabled'}))
        _send_cfn_response(event, context, 'SUCCESS')
    except Exception as exc:
        logger.error(json.dumps({'level': 'ERROR', 'error': str(exc)}))
        _send_cfn_response(event, context, 'FAILED', {'Error': str(exc)})
```

- [ ] **Step 2: Commit**

```bash
git add services/ai-assistant/src/enable_bedrock_logging/
git commit -m "feat(ai-assistant): add Bedrock model invocation logging Custom Resource"
```

---

## Task 7: SAM template

Wire all resources together.

**Files:**
- Create: `services/ai-assistant/template.yaml`

- [ ] **Step 1: Write template**

`services/ai-assistant/template.yaml`:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: "Stack for todo-houessou-com ai-assistant service"

Parameters:
  CognitoUserPoolId:
    Type: String
    Description: Cognito User Pool ID for JWT validation

Globals:
  Function:
    Runtime: python3.12
    Tracing: Active

Resources:

  # ── DynamoDB ──────────────────────────────────────────────────────────────

  BotTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "BotTable-${AWS::StackName}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  # ── Lambda Functions ──────────────────────────────────────────────────────

  AuthorizerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-authorizer"
      CodeUri: src/authorizer/
      Handler: handler.lambda_handler
      Timeout: 10
      Environment:
        Variables:
          COGNITO_USER_POOL_ID: !Ref CognitoUserPoolId
          COGNITO_REGION: !Sub "${AWS::Region}"

  WebSocketHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-websocket-handler"
      CodeUri: src/websocket_handler/
      Handler: handler.lambda_handler
      Timeout: 30
      Environment:
        Variables:
          BOT_TABLE: !Ref BotTable
          AGENT_ID: VLLFJVDUBD
          AGENT_ALIAS_ID: JLCNDHYLCT
          ENABLE_TRACE: "false"
          WS_ENDPOINT: !Sub "https://${ChatbotWebSocketApi}.execute-api.${AWS::Region}.amazonaws.com/production"
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:PutItem
                - dynamodb:DeleteItem
              Resource: !GetAtt BotTable.Arn
            - Effect: Allow
              Action: bedrock:InvokeAgent
              Resource: !Sub "arn:aws:bedrock:${AWS::Region}:${AWS::AccountId}:agent-alias/VLLFJVDUBD/JLCNDHYLCT"
            - Effect: Allow
              Action: execute-api:ManageConnections
              Resource: !Sub "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ChatbotWebSocketApi}/production/POST/@connections/*"

  ActionGroupHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-action-group"
      CodeUri: src/action_group/
      Handler: handler.lambda_handler
      Timeout: 30
      Environment:
        Variables:
          TODO_TABLE: !ImportValue "todo-houessou-com-TodoTable"
          TODO_TABLE_REGION: !Sub "${AWS::Region}"
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:Query
                - dynamodb:PutItem
                - dynamodb:UpdateItem
              Resource:
                - !ImportValue "todo-houessou-com-TodoTableArn"
                - !Sub
                  - "${TableArn}/index/*"
                  - TableArn: !ImportValue "todo-houessou-com-TodoTableArn"

  EnableBedrockLoggingFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-enable-bedrock-logging"
      CodeUri: src/enable_bedrock_logging/
      Handler: handler.lambda_handler
      Timeout: 30
      Environment:
        Variables:
          LOGGING_ROLE_ARN: !GetAtt BedrockLoggingRole.Arn
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: bedrock:PutModelInvocationLoggingConfiguration
              Resource: "*"

  # ── WebSocket API ─────────────────────────────────────────────────────────

  ChatbotWebSocketApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Name: !Sub "${AWS::StackName}-websocket"
      ProtocolType: WEBSOCKET
      RouteSelectionExpression: "$request.body.action"

  ChatbotAuthorizer:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      AuthorizerType: REQUEST
      AuthorizerUri: !Sub "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${AuthorizerFunction.Arn}/invocations"
      IdentitySource:
        - route.request.querystring.token
      Name: CognitoJwtAuthorizer

  ConnectIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      IntegrationType: AWS_PROXY
      IntegrationUri: !Sub "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${WebSocketHandlerFunction.Arn}/invocations"

  DisconnectIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      IntegrationType: AWS_PROXY
      IntegrationUri: !Sub "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${WebSocketHandlerFunction.Arn}/invocations"

  DefaultIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      IntegrationType: AWS_PROXY
      IntegrationUri: !Sub "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${WebSocketHandlerFunction.Arn}/invocations"

  ConnectRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      RouteKey: $connect
      AuthorizationType: CUSTOM
      AuthorizerId: !Ref ChatbotAuthorizer
      Target: !Sub "integrations/${ConnectIntegration}"

  DisconnectRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      RouteKey: $disconnect
      AuthorizationType: NONE
      Target: !Sub "integrations/${DisconnectIntegration}"

  DefaultRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      RouteKey: $default
      AuthorizationType: NONE
      Target: !Sub "integrations/${DefaultIntegration}"

  ChatbotDeployment:
    Type: AWS::ApiGatewayV2::Deployment
    DependsOn:
      - ConnectRoute
      - DisconnectRoute
      - DefaultRoute
    Properties:
      ApiId: !Ref ChatbotWebSocketApi

  ChatbotStage:
    Type: AWS::ApiGatewayV2::Stage
    Properties:
      ApiId: !Ref ChatbotWebSocketApi
      DeploymentId: !Ref ChatbotDeployment
      StageName: production

  # ── Lambda Permissions ────────────────────────────────────────────────────

  AuthorizerInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt AuthorizerFunction.Arn
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ChatbotWebSocketApi}/*"

  WebSocketHandlerInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt WebSocketHandlerFunction.Arn
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ChatbotWebSocketApi}/*"

  # ── Bedrock Observability ─────────────────────────────────────────────────

  BedrockInvocationLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: /aws/bedrock/model-invocations
      RetentionInDays: 7

  BedrockLoggingRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "${AWS::StackName}-bedrock-logging-role"
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: BedrockCWLogsPolicy
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: !GetAtt BedrockInvocationLogGroup.Arn

  BedrockLoggingCustomResource:
    Type: AWS::CloudFormation::CustomResource
    DependsOn:
      - BedrockInvocationLogGroup
      - BedrockLoggingRole
    Properties:
      ServiceToken: !GetAtt EnableBedrockLoggingFunction.Arn

  EnableBedrockLoggingInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt EnableBedrockLoggingFunction.Arn
      Action: lambda:InvokeFunction
      Principal: cloudformation.amazonaws.com

  # ── Outputs ───────────────────────────────────────────────────────────────

Outputs:
  WebSocketEndpoint:
    Description: "WebSocket API endpoint — use as VITE_CHATBOT_WS_ENDPOINT"
    Value: !Sub "wss://${ChatbotWebSocketApi}.execute-api.${AWS::Region}.amazonaws.com/production"
    Export:
      Name: !Sub "${AWS::StackName}-WebSocketEndpoint"
  ActionGroupFunctionArn:
    Description: "ARN for Bedrock action group — update in Bedrock console"
    Value: !GetAtt ActionGroupHandlerFunction.Arn
    Export:
      Name: !Sub "${AWS::StackName}-ActionGroupFunctionArn"
```

- [ ] **Step 2: Validate template**

```bash
cd services/ai-assistant
sam validate --template template.yaml --lint
```

Expected: `template.yaml is a valid SAM Template`

- [ ] **Step 3: Commit**

```bash
git add services/ai-assistant/template.yaml
git commit -m "feat(ai-assistant): add SAM template with WebSocket API, BotTable, and observability"
```

---

## Task 8: samconfig.toml

**Files:**
- Create: `services/ai-assistant/samconfig.toml`

- [ ] **Step 1: Write samconfig**

> **Note:** The ai-assistant service must deploy to `us-east-1` (same region as the
> Bedrock Agent). The main-service's `TodoTable` must also be accessible from `us-east-1`.
> If the main-service stack is in a different region, set `TODO_TABLE_REGION` accordingly
> and ensure cross-region DynamoDB access is working (or redeploy main-service to `us-east-1`).

`services/ai-assistant/samconfig.toml`:

```toml
version = 0.1

[default]
[default.deploy]
[default.deploy.parameters]
stack_name = "todo-houessou-com-ai-assistant"
s3_bucket = "aws-sam-cli-managed-default-samclisourcebucket-1i1fu54xc3wfs"
s3_prefix = "todo-houessou-com-ai-assistant"
region = "us-east-1"
capabilities = "CAPABILITY_IAM CAPABILITY_NAMED_IAM"
parameter_overrides = "CognitoUserPoolId=<REPLACE_WITH_YOUR_COGNITO_POOL_ID>"
image_repositories = []
```

Replace `<REPLACE_WITH_YOUR_COGNITO_POOL_ID>` with the actual Cognito User Pool ID
(visible in the main-service SAM template or the AWS Cognito console).

- [ ] **Step 2: Commit**

```bash
git add services/ai-assistant/samconfig.toml
git commit -m "chore(ai-assistant): add samconfig.toml for us-east-1 deployment"
```

---

## Task 9: Build and deploy

- [ ] **Step 1: Build**

```bash
cd services/ai-assistant
sam build
```

Expected: `Build Succeeded` with all four functions listed.

- [ ] **Step 2: Deploy**

```bash
sam deploy
```

Expected: CloudFormation stack `todo-houessou-com-ai-assistant` created/updated
with `CREATE_COMPLETE`. The output `WebSocketEndpoint` shows the new wss:// URL.
The output `ActionGroupFunctionArn` shows the new action group Lambda ARN.

- [ ] **Step 3: Note outputs**

```bash
aws cloudformation describe-stacks \
  --stack-name todo-houessou-com-ai-assistant \
  --region us-east-1 \
  --query "Stacks[0].Outputs" \
  --output table \
  --no-cli-pager \
  --profile da
```

Note the `WebSocketEndpoint` value (wss://...) — needed for Task 11.
Note the `ActionGroupFunctionArn` — needed for the Bedrock console update.

- [ ] **Step 4: Update Bedrock Agent action group Lambda in console**

1. Go to AWS Console → Bedrock → Agents → `todo2` (VLLFJVDUBD)
2. Click **Edit**
3. Under **Action groups** → `todos` → click to edit
4. Under **Action group invocation** → change Lambda function to the new
   `todo-houessou-com-ai-assistant-action-group` function
5. Click **Save**
6. Back on agent page: click **Prepare** (required after any agent change)
7. Verify status shows **PREPARED**

- [ ] **Step 5: Update Bedrock Agent model to Nova Micro**

1. On the same agent edit page → **Model details** → click edit (pencil icon)
2. Select **Amazon Nova Micro** (`amazon.nova-micro-v1:0`)
3. Save → **Prepare** again
4. Verify status shows **PREPARED**

- [ ] **Step 6: Commit deploy outputs note**

```bash
git add services/ai-assistant/samconfig.toml  # in case Cognito ID was filled in
git commit -m "chore(ai-assistant): update samconfig with Cognito pool ID after deploy"
```

---

## Task 10: Frontend — chatbot.ts

Replace the per-message WebSocket with a persistent connection.

**Files:**
- Modify: `apps/web/src/chatbot.ts`

- [ ] **Step 1: Replace chatbot.ts entirely**

`apps/web/src/chatbot.ts`:

```typescript
import { config } from './config';

type Sender = 'user' | 'bot';

let ws: WebSocket | null = null;

export function openChatSession(): void {
    if (ws && ws.readyState === WebSocket.OPEN) return; // already connected

    const stored = localStorage.getItem('sessionTokens');
    if (!stored) {
        window.location.href = './index.html';
        return;
    }
    const tokens = JSON.parse(stored);
    const token: string = tokens?.IdToken?.jwtToken ?? '';
    if (!token) {
        window.location.href = './index.html';
        return;
    }

    ws = new WebSocket(`${config.chatbotWsEndpoint}?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
        console.log('[chatbot] WebSocket connected');
    };

    ws.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data as string);
        removeTypingIndicator();
        displayMessage(data.response, 'bot');
    };

    ws.onerror = () => {
        removeTypingIndicator();
        displayMessage('Connection error. Please refresh the page.', 'bot');
    };

    ws.onclose = () => {
        console.log('[chatbot] WebSocket closed');
        ws = null;
    };
}

export function closeChatSession(): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    ws = null;
}

export function displayMessage(text: string, sender: Sender = 'user'): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);

    const botIcon = '<img src="public/img/bot-icon.svg" alt="Bot" style="width: 20px; height: 20px;"> ';
    const icon = sender === 'user' ? '&#128100; ' : botIcon;
    messageElement.innerHTML = icon + text;

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

export function displayTypingIndicator(): void {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    let typingIndicator = document.getElementById('typingIndicator');
    if (!typingIndicator) {
        typingIndicator = document.createElement('div');
        typingIndicator.classList.add('message', 'typing');
        typingIndicator.id = 'typingIndicator';
        typingIndicator.textContent = '...';
        chatMessages.appendChild(typingIndicator);
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

export function removeTypingIndicator(): void {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) typingIndicator.remove();
}

export function sendMessage(): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        displayMessage('Not connected. Please open the chat panel again.', 'bot');
        return;
    }

    const userInput = document.getElementById('userInput') as HTMLInputElement;
    const message = userInput.value.trim();
    if (!message) return;

    userInput.value = '';
    displayMessage(message, 'user');
    displayTypingIndicator();

    ws.send(JSON.stringify({ human: message }));
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/chatbot.ts
git commit -m "feat(web): persistent WebSocket connection per chat session, remove userID from payload"
```

---

## Task 11: Frontend — home.ts integration

Wire `openChatSession` / `closeChatSession` into the chat panel toggle.

**Files:**
- Modify: `apps/web/src/pages/home.ts`

- [ ] **Step 1: Add imports and update chat toggle**

Add `openChatSession` and `closeChatSession` to the import at the top of
`apps/web/src/pages/home.ts`.

Replace line 3:

```typescript
import { sendMessage } from '../chatbot';
```

With:

```typescript
import { sendMessage, openChatSession, closeChatSession } from '../chatbot';
```

- [ ] **Step 2: Update the chat tab click handler**

Replace the existing `chatTab?.addEventListener('click', ...)` block (lines 18-22):

```typescript
    chatTab?.addEventListener('click', () => {
        if (!chatContainer) return;
        const isOpen = chatContainer.style.display === 'flex';
        if (isOpen) {
            chatContainer.style.display = 'none';
            closeChatSession();
        } else {
            chatContainer.style.display = 'flex';
            openChatSession();
            (document.getElementById('userInput') as HTMLInputElement)?.focus();
        }
    });
```

- [ ] **Step 3: Add beforeunload handler inside DOMContentLoaded**

Add this line at the end of the `document.addEventListener('DOMContentLoaded', ...)` callback,
just before the closing `}`  (after line 91, before the closing `}`):

```typescript
    window.addEventListener('beforeunload', closeChatSession);
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/pages/home.ts
git commit -m "feat(web): open/close WebSocket session on chat panel toggle"
```

---

## Task 12: Update frontend config and build

**Files:**
- Modify: `apps/web/.env` (or `.env.production`) — update `VITE_CHATBOT_WS_ENDPOINT`

- [ ] **Step 1: Update WebSocket endpoint in environment config**

In `apps/web/.env` (or whichever env file is used for builds), set:

```
VITE_CHATBOT_WS_ENDPOINT=wss://<api-id>.execute-api.us-east-1.amazonaws.com/production
```

Use the `WebSocketEndpoint` value from Task 9 Step 3.

- [ ] **Step 2: Build frontend**

```bash
cd apps/web
npm run build
```

Expected: `dist/` produced with no TypeScript errors.

- [ ] **Step 3: Deploy frontend (existing pipeline)**

Push to the branch that triggers the frontend GitHub Actions pipeline, or deploy
manually using the existing S3/CloudFront workflow.

- [ ] **Step 4: Smoke test**

1. Open the todo app in browser
2. Log in with a valid Cognito account
3. Open the chat panel — browser DevTools Network tab should show a WebSocket
   connection established (Status: 101)
4. Send "show me my todos" — response should appear within ~3 seconds
5. Send a second message — it should use the same WebSocket connection (no new
   101 handshake in DevTools)
6. Close and reopen the chat panel — a new WebSocket connection should appear
7. Send a message — the agent should remember context from the earlier session
   (sessionId was preserved in DynamoDB)

- [ ] **Step 5: Final commit**

```bash
git add apps/web/.env  # only if not gitignored
git commit -m "chore(web): update VITE_CHATBOT_WS_ENDPOINT to new ai-assistant stack endpoint"
```

---

## Notes

- **Region:** The ai-assistant stack deploys to `us-east-1` (where the Bedrock Agent lives).
  The main-service exports (`todo-houessou-com-TodoTable` and `todo-houessou-com-TodoTableArn`)
  must be accessible from `us-east-1`. If the main-service stack is in `ca-central-1`,
  either redeploy it to `us-east-1` or use cross-region DynamoDB access with
  `TODO_TABLE_REGION=ca-central-1` env var and ensure IAM allows cross-region access.

- **Bedrock Agent model change** in Task 9 requires the agent to be re-prepared.
  Do not skip the **Prepare** step — the agent will silently use the old model
  until it is prepared.

- **`ENABLE_TRACE`:** Keep `false` in production. Set to `true` only for debugging.
  Trace output significantly increases agent latency and CloudWatch log volume.

- **Cognito token in query string:** The `?token=` approach is the only way to pass
  auth headers on browser WebSocket connections. Treat this as a short-lived credential
  (Cognito ID tokens expire in 1 hour). The connection itself does not re-auth after
  `$connect`.
