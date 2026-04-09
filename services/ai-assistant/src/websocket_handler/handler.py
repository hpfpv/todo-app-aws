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
