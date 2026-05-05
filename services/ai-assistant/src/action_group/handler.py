import boto3
import json
import logging
import os
import uuid
from datetime import datetime
from urllib.parse import unquote

client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
s3_client = boto3.client('s3')
cloudwatch = boto3.client('cloudwatch')

TODO_TABLE = os.environ['TODO_TABLE']
FILES_TABLE = os.environ.get('FILES_TABLE', '')
FILES_BUCKET = os.environ.get('FILES_BUCKET', '')
FILES_BUCKET_CDN = os.environ.get('FILES_BUCKET_CDN', '')
METRICS_NAMESPACE = 'LLMSecurity/TodoChatbot'

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _emit_metric(name, dimensions=None):
    try:
        cloudwatch.put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[{
                'MetricName': name,
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions or [],
            }],
        )
    except Exception as exc:
        logger.warning(json.dumps({'action': 'metric_failed', 'metric': name, 'error': str(exc)}))


def _read_user_id(event):
    """Authoritative userID from Bedrock session attributes — never from parameters."""
    psa = event.get('promptSessionAttributes') or {}
    sa = event.get('sessionAttributes') or {}
    user_id = psa.get('userID') or sa.get('userID')
    return user_id.strip() if user_id else None


def _err(event, message):
    return {
        'response': {
            'actionGroup': event.get('actionGroup', 'TodoActions'),
            'function': event.get('function', ''),
            'functionResponse': {'responseBody': {'TEXT': {'body': json.dumps({'error': message})}}},
        }
    }


def _assert_owns_todo(user_id, todo_id):
    resp = client.get_item(TableName=TODO_TABLE, Key={'todoID': {'S': todo_id}})
    item = resp.get('Item')
    if not item:
        return False
    return item.get('userID', {}).get('S') == user_id


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
    response = client.get_item(TableName=TODO_TABLE, Key={'todoID': {'S': todoID}})
    return _todo_from_item(response['Item'])


def getTodos(userID):
    response = client.query(
        TableName=TODO_TABLE,
        IndexName='userIDIndex',
        KeyConditions={'userID': {'AttributeValueList': [{'S': userID}], 'ComparisonOperator': 'EQ'}},
    )
    todos = [_todo_from_item(item) for item in response['Items']]
    todos = sorted(todos, key=lambda i: i['dateCreated'], reverse=True)
    todos = sorted(todos, key=lambda i: i['dateDue'])
    todos = sorted(todos, key=lambda i: i['completed'])
    logger.info(json.dumps({'action': 'getTodos', 'userID': userID[:3] + '***', 'count': len(todos)}))
    slim = [{'todoID': t['todoID'], 'title': t['title'], 'description': t['description'], 'dateDue': t['dateDue'], 'completed': t['completed']} for t in todos]
    return {'todos': slim}


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
    client.put_item(TableName=TODO_TABLE, Item=item)
    logger.info(json.dumps({'action': 'addTodo', 'userID': userID[:3] + '***'}))
    return {'status': 'success'}


def addTodoNotes(todoID, notes):
    client.update_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET notes = :n',
        ExpressionAttributeValues={':n': {'S': notes}},
    )
    return {'Update': 'Success'}


def completeTodo(todoID):
    client.update_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET completed = :b',
        ExpressionAttributeValues={':b': {'BOOL': True}},
    )
    return {'Update': 'Success'}


def deleteTodo(userID, todoID):
    if FILES_TABLE:
        resp = client.query(
            TableName=FILES_TABLE,
            IndexName='todoIDIndex',
            KeyConditions={'todoID': {'AttributeValueList': [{'S': todoID}], 'ComparisonOperator': 'EQ'}},
        )
        for item in resp.get('Items', []):
            file_id = item['fileID']['S']
            file_path = item['filePath']['S']
            if FILES_BUCKET and FILES_BUCKET_CDN:
                s3_key = unquote(file_path.replace(f'https://{FILES_BUCKET_CDN}/', ''))
                try:
                    s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
                except Exception as e:
                    logger.warning(json.dumps({'action': 'deleteTodo_s3_warn', 'fileID': file_id, 'error': str(e)}))
            client.delete_item(TableName=FILES_TABLE, Key={'fileID': {'S': file_id}})
    client.delete_item(TableName=TODO_TABLE, Key={'todoID': {'S': todoID}})
    logger.info(json.dumps({'action': 'deleteTodo', 'userID': userID[:3] + '***', 'todoID': todoID}))
    return {'status': 'success'}


def listTodoFiles(todoID):
    if not FILES_TABLE:
        return {'files': []}
    resp = client.query(
        TableName=FILES_TABLE,
        IndexName='todoIDIndex',
        KeyConditions={'todoID': {'AttributeValueList': [{'S': todoID}], 'ComparisonOperator': 'EQ'}},
    )
    files = [{'fileID': i['fileID']['S'], 'fileName': i['fileName']['S'], 'filePath': i['filePath']['S']} for i in resp.get('Items', [])]
    return {'files': files}


def addTodoFile(todoID, fileName, fileUrl):
    if not FILES_TABLE:
        return {'error': 'Files service not configured'}
    file_id = str(uuid.uuid4())
    client.put_item(
        TableName=FILES_TABLE,
        Item={
            'fileID': {'S': file_id},
            'todoID': {'S': todoID},
            'fileName': {'S': fileName},
            'filePath': {'S': fileUrl},
        },
    )
    return {'status': 'success', 'fileID': file_id}


def deleteTodoFile(todoID, fileID):
    if not FILES_TABLE:
        return {'error': 'Files service not configured'}
    resp = client.get_item(TableName=FILES_TABLE, Key={'fileID': {'S': fileID}})
    item = resp.get('Item')
    if not item:
        return {'status': 'not_found', 'fileID': fileID}
    file_path = item['filePath']['S']
    if FILES_BUCKET and FILES_BUCKET_CDN:
        s3_key = unquote(file_path.replace(f'https://{FILES_BUCKET_CDN}/', ''))
        try:
            s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
        except Exception as e:
            logger.warning(json.dumps({'action': 'deleteTodoFile_s3_warn', 'fileID': fileID, 'error': str(e)}))
    client.delete_item(TableName=FILES_TABLE, Key={'fileID': {'S': fileID}})
    return {'status': 'success'}


def lambda_handler(event, context):
    logger.info(json.dumps({'event': {'function': event.get('function'), 'actionGroup': event.get('actionGroup')}}))

    user_id = _read_user_id(event)
    if not user_id:
        _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Reason', 'Value': 'NoSessionUserId'}])
        return _err(event, 'session userID missing')

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    function = event['function']

    if function == 'getTodos':
        body = getTodos(user_id)

    elif function == 'getTodo':
        todo_id = parameters['todoID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'getTodo'}])
            return _err(event, 'not authorized for this todo')
        body = getTodo(todo_id)

    elif function == 'addTodo':
        body = addTodo(user_id, {
            'title': parameters['title'],
            'description': parameters['description'],
            'dateDue': parameters['dateDue'],
        })

    elif function == 'addTodoNotes':
        todo_id = parameters['todoID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'addTodoNotes'}])
            return _err(event, 'not authorized for this todo')
        body = addTodoNotes(todo_id, parameters['notes'])

    elif function == 'completeTodo':
        todo_id = parameters['todoID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'completeTodo'}])
            return _err(event, 'not authorized for this todo')
        body = completeTodo(todo_id)

    elif function == 'deleteTodo':
        todo_id = parameters['todoID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'deleteTodo'}])
            return _err(event, 'not authorized for this todo')
        body = deleteTodo(user_id, todo_id)

    elif function == 'listTodoFiles':
        todo_id = parameters['todoID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'listTodoFiles'}])
            return _err(event, 'not authorized for this todo')
        body = listTodoFiles(todo_id)

    elif function == 'addTodoFile':
        todo_id = parameters['todoID']
        file_url = parameters['fileUrl']
        allowlist_prefix = f'https://{FILES_BUCKET_CDN}/' if FILES_BUCKET_CDN else None
        if not allowlist_prefix or not file_url.startswith(allowlist_prefix):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'addTodoFile_url'}])
            return _err(event, 'fileUrl not on the allowed CDN')
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'addTodoFile'}])
            return _err(event, 'not authorized for this todo')
        body = addTodoFile(todo_id, parameters['fileName'], file_url)

    elif function == 'deleteTodoFile':
        todo_id = parameters['todoID']
        file_id = parameters['fileID']
        if not _assert_owns_todo(user_id, todo_id):
            _emit_metric('UnauthorizedActionAttempt', [{'Name': 'Function', 'Value': 'deleteTodoFile'}])
            return _err(event, 'not authorized for this todo')
        body = deleteTodoFile(todo_id, file_id)

    else:
        body = {'error': f'{event.get("actionGroup", "")}::{function} is not a valid function'}

    return {
        'response': {
            'actionGroup': event['actionGroup'],
            'function': function,
            'functionResponse': {'responseBody': {'TEXT': {'body': json.dumps(body)}}},
        }
    }
