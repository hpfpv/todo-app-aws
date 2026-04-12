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

WS_ENDPOINT = os.environ.get('WS_ENDPOINT', '')
_api_gw_mgmt = boto3.client('apigatewaymanagementapi', endpoint_url=WS_ENDPOINT) if WS_ENDPOINT else None


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

    if not agent_answer:
        logger.warning(json.dumps({
            'level': 'WARN', 'route': '$default', 'action': 'empty_agent_response',
            'connectionId': connection_id,
        }))
        agent_answer = 'Sorry, I could not get a response. Please try again.'

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
    if _api_gw_mgmt:
        try:
            _api_gw_mgmt.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'response': agent_answer}),
            )
        except _api_gw_mgmt.exceptions.GoneException:
            logger.info(json.dumps({
                'level': 'INFO', 'action': 'connection_gone',
                'connectionId': connection_id,
            }))

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
