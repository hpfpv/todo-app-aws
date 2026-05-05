import boto3
import json
import logging
import os
import re
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

WS_ENDPOINT = os.environ.get('WS_ENDPOINT', '')
_api_gw_mgmt = boto3.client('apigatewaymanagementapi', endpoint_url=WS_ENDPOINT) if WS_ENDPOINT else None

cloudwatch = boto3.client('cloudwatch')
METRICS_NAMESPACE = 'LLMSecurity/TodoChatbot'
MAX_INPUT_LEN = 1000
RATE_LIMIT_WINDOW_SECONDS = 300
RATE_LIMIT_MAX = 30


def _check_rate_limit(user_id):
    """Returns True if request is allowed; False if rate-limited. Fixed-window per user."""
    pk = f'ratelimit#{user_id}'
    now = int(time.time())
    ttl = now + RATE_LIMIT_WINDOW_SECONDS
    resp = dynamodb.update_item(
        TableName=BOT_TABLE,
        Key={'pk': {'S': pk}},
        UpdateExpression='ADD #c :one SET #t = if_not_exists(#t, :ttl)',
        ExpressionAttributeNames={'#c': 'count', '#t': 'ttl'},
        ExpressionAttributeValues={':one': {'N': '1'}, ':ttl': {'N': str(ttl)}},
        ReturnValues='ALL_NEW',
    )
    count = int(resp['Attributes']['count']['N'])
    return count <= RATE_LIMIT_MAX


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"you\s+are\s+now",
    r"(reveal|repeat|print|output)\s+(your\s+)?system\s+prompt",
    r"<!--.{0,300}(ignore|override|system)",
    r"\[SYSTEM\s*(OVERRIDE|COMMAND|INSTRUCTION)\]",
    r"forget\s+(everything|your\s+training|your\s+instructions)",
]

OUTPUT_BLOCKLIST_PATTERNS = [
    r"you\s+are\s+tasko",
    r"your\s+tools\s+are",
    r"action\s*group",
    r"system\s+prompt",
    r"\$prompt_session",
]


def _scan_output_for_leak(text):
    for pat in OUTPUT_BLOCKLIST_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return pat
    return None


def _emit_metric(name, dimensions=None):
    try:
        cloudwatch.put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[{'MetricName': name, 'Value': 1, 'Unit': 'Count', 'Dimensions': dimensions or []}],
        )
    except Exception as exc:
        logger.warning(json.dumps({'action': 'metric_failed', 'metric': name, 'error': str(exc)}))


def _scan_for_injection(text):
    for pat in INJECTION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE | re.DOTALL):
            return pat
    return None


def _post_error(connection_id, code, text):
    if not _api_gw_mgmt:
        return
    try:
        _api_gw_mgmt.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({'type': 'error', 'code': code, 'text': text}),
        )
    except Exception:
        pass


def _connect(connection_id, user_id, fresh=False):
    now = int(time.time())
    # Check for an existing session for this user (skip reuse when fresh=True)
    if not fresh:
        response = dynamodb.get_item(
            TableName=BOT_TABLE,
            Key={'pk': {'S': user_id}},
        )
        item = response.get('Item')
    else:
        item = None

    if item and int(item['ttl']['N']) > now:
        session_id = item['sessionId']['S']
        logger.info(json.dumps({
            'level': 'INFO', 'route': '$connect', 'action': 'reuse_session',
            'connectionId': connection_id, 'userIdPrefix': user_id[:3] + '***',
        }))
    else:
        session_id = str(uuid.uuid4())
        logger.info(json.dumps({
            'level': 'INFO', 'route': '$connect',
            'action': 'fresh_session' if fresh else 'new_session',
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

    # Rate limit (per-user fixed window)
    if not _check_rate_limit(user_id):
        _emit_metric('RateLimited')
        _post_error(connection_id, 'RateLimited',
                    f'Slow down — {RATE_LIMIT_MAX} messages per {RATE_LIMIT_WINDOW_SECONDS // 60} minutes.')
        return {'statusCode': 200}

    # Length cap
    if len(human) > MAX_INPUT_LEN:
        _emit_metric('LengthExceeded')
        _post_error(connection_id, 'LengthExceeded', f'Message too long. Max {MAX_INPUT_LEN} characters.')
        return {'statusCode': 200}

    # Regex injection scan
    matched = _scan_for_injection(human)
    if matched:
        _emit_metric('InjectionBlocked', [{'Name': 'Pattern', 'Value': matched[:64]}])
        _post_error(connection_id, 'InjectionBlocked',
                    "I'm here to help with your todos. I can't help with that request.")
        return {'statusCode': 200}

    # Strip HTML comments and wrap in <query>
    human_clean = re.sub(r"<!--.*?-->", "", human, flags=re.DOTALL).strip()
    input_text = f"<query>\n{human_clean}\n</query>"

    # Invoke Bedrock Agent — userID is injected via promptSessionAttributes,
    # referenced as $prompt_session.userID$ in the agent instruction
    agent_response = bedrock_agent_runtime.invoke_agent(
        inputText=input_text,
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        enableTrace=ENABLE_TRACE,
        endSession=False,
        sessionState={
            'promptSessionAttributes': {'userID': user_id},
        },
    )

    agent_answer = ''
    for event in agent_response['completion']:
        if 'chunk' in event:
            chunk_text = event['chunk']['bytes'].decode('utf-8')
            agent_answer += chunk_text
            if _api_gw_mgmt:
                try:
                    _api_gw_mgmt.post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({'type': 'chunk', 'text': chunk_text}),
                    )
                except _api_gw_mgmt.exceptions.GoneException:
                    logger.info(json.dumps({'level': 'INFO', 'action': 'connection_gone', 'connectionId': connection_id}))
                    return {'statusCode': 200}
        elif 'trace' in event and ENABLE_TRACE:
            logger.info(json.dumps({'trace': event['trace']}))

    if not agent_answer:
        agent_answer = 'Sorry, I could not get a response. Please try again.'
        if _api_gw_mgmt:
            try:
                _api_gw_mgmt.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps({'type': 'chunk', 'text': agent_answer}),
                )
            except Exception:
                pass

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

    leaked = _scan_output_for_leak(agent_answer)
    if leaked:
        _emit_metric('OutputBlocked', [{'Name': 'Pattern', 'Value': leaked[:64]}])
        _post_error(connection_id, 'OutputBlocked', "I'm unable to share that information.")
        return {'statusCode': 200}

    if _api_gw_mgmt:
        try:
            _api_gw_mgmt.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'type': 'done'}),
            )
        except Exception:
            pass

    return {'statusCode': 200}


def lambda_handler(event, context):
    route = event['requestContext']['routeKey']
    connection_id = event['requestContext']['connectionId']

    if route == '$connect':
        user_id = event['requestContext'].get('authorizer', {}).get('userID', 'unknown')
        fresh = event.get('queryStringParameters', {}).get('fresh') == '1'
        return _connect(connection_id, user_id, fresh=fresh)
    elif route == '$disconnect':
        return _disconnect(connection_id)
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
            if _api_gw_mgmt:
                try:
                    _api_gw_mgmt.post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({'response': 'Sorry, something went wrong. Please try again.'}),
                    )
                except Exception:
                    pass
            raise
