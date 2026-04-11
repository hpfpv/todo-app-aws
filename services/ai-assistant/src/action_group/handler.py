import boto3
import json
import logging
import os
import uuid
from datetime import datetime

client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
files_client = boto3.client('dynamodb', region_name=os.environ.get('TODO_TABLE_REGION', 'us-east-1'))
s3_client = boto3.client('s3')

TODO_TABLE = os.environ['TODO_TABLE']
FILES_TABLE = os.environ.get('FILES_TABLE', '')
FILES_BUCKET = os.environ.get('FILES_BUCKET', '')
FILES_BUCKET_CDN = os.environ.get('FILES_BUCKET_CDN', '')

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
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}}
    )
    return _todo_from_item(response['Item'])


def getTodos(userID):
    response = client.query(
        TableName=TODO_TABLE,
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
    slim = [
        {
            'todoID': t['todoID'],
            'title': t['title'],
            'description': t['description'],
            'dateDue': t['dateDue'],
            'completed': t['completed'],
        }
        for t in todos
    ]
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
    return json.dumps({'status': 'success'})


def addTodoNotes(todoID, notes):
    client.update_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET notes = :n',
        ExpressionAttributeValues={':n': {'S': notes}}
    )
    logger.info(json.dumps({'action': 'addTodoNotes', 'todoID': todoID}))
    return json.dumps({'Update': 'Success'})


def completeTodo(todoID):
    client.update_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
        UpdateExpression='SET completed = :b',
        ExpressionAttributeValues={':b': {'BOOL': True}}
    )
    logger.info(json.dumps({'action': 'completeTodo', 'todoID': todoID}))
    return json.dumps({'Update': 'Success'})


def deleteTodo(userID, todoID):
    # Delete all associated files first
    if FILES_TABLE:
        resp = files_client.query(
            TableName=FILES_TABLE,
            IndexName='todoIDIndex',
            KeyConditions={
                'todoID': {
                    'AttributeValueList': [{'S': todoID}],
                    'ComparisonOperator': 'EQ',
                }
            },
        )
        for item in resp.get('Items', []):
            file_id = item['fileID']['S']
            file_path = item['filePath']['S']
            if FILES_BUCKET and FILES_BUCKET_CDN:
                s3_key = file_path.replace(f'https://{FILES_BUCKET_CDN}/', '').replace('%40', '@')
                try:
                    s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
                except Exception as e:
                    logger.warning(json.dumps({'action': 'deleteTodo_s3_warn', 'fileID': file_id, 'error': str(e)}))
            files_client.delete_item(
                TableName=FILES_TABLE,
                Key={'fileID': {'S': file_id}},
            )
    client.delete_item(
        TableName=TODO_TABLE,
        Key={'todoID': {'S': todoID}},
    )
    logger.info(json.dumps({'action': 'deleteTodo', 'userID': userID[:3] + '***', 'todoID': todoID}))
    return json.dumps({'status': 'success'})


def listTodoFiles(todoID):
    if not FILES_TABLE:
        return {'files': []}
    resp = files_client.query(
        TableName=FILES_TABLE,
        IndexName='todoIDIndex',
        KeyConditions={
            'todoID': {
                'AttributeValueList': [{'S': todoID}],
                'ComparisonOperator': 'EQ',
            }
        },
    )
    files = [
        {
            'fileID': item['fileID']['S'],
            'fileName': item['fileName']['S'],
            'filePath': item['filePath']['S'],
        }
        for item in resp.get('Items', [])
    ]
    logger.info(json.dumps({'action': 'listTodoFiles', 'todoID': todoID, 'count': len(files)}))
    return {'files': files}


def addTodoFile(todoID, fileName, fileUrl):
    """Register a file that has already been uploaded to S3/CDN."""
    if not FILES_TABLE:
        return json.dumps({'error': 'Files service not configured'})
    file_id = str(uuid.uuid4())
    files_client.put_item(
        TableName=FILES_TABLE,
        Item={
            'fileID': {'S': file_id},
            'todoID': {'S': todoID},
            'fileName': {'S': fileName},
            'filePath': {'S': fileUrl},
        },
    )
    logger.info(json.dumps({'action': 'addTodoFile', 'todoID': todoID, 'fileName': fileName}))
    return json.dumps({'status': 'success', 'fileID': file_id})


def deleteTodoFile(todoID, fileID):
    if not FILES_TABLE:
        return json.dumps({'error': 'Files service not configured'})
    resp = files_client.get_item(
        TableName=FILES_TABLE,
        Key={'fileID': {'S': fileID}},
    )
    item = resp.get('Item')
    if item:
        file_path = item['filePath']['S']
        if FILES_BUCKET and FILES_BUCKET_CDN:
            s3_key = file_path.replace(f'https://{FILES_BUCKET_CDN}/', '').replace('%40', '@')
            try:
                s3_client.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
            except Exception as e:
                logger.warning(json.dumps({'action': 'deleteTodoFile_s3_warn', 'fileID': fileID, 'error': str(e)}))
        files_client.delete_item(
            TableName=FILES_TABLE,
            Key={'fileID': {'S': fileID}},
        )
    logger.info(json.dumps({'action': 'deleteTodoFile', 'todoID': todoID, 'fileID': fileID}))
    return json.dumps({'status': 'success'})


def lambda_handler(event, context):
    logger.info(json.dumps({'event': event}))
    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    function = event['function']

    if function == 'getTodos':
        body = getTodos(parameters['userID'])
    elif function == 'getTodo':
        body = getTodo(parameters['todoID'])
    elif function == 'addTodo':
        body = addTodo(parameters['userID'], {
            'title': parameters['title'],
            'description': parameters['description'],
            'dateDue': parameters['dateDue'],
        })
    elif function == 'addTodoNotes':
        body = addTodoNotes(parameters['todoID'], parameters['notes'])
    elif function == 'completeTodo':
        body = completeTodo(parameters['todoID'])
    elif function == 'deleteTodo':
        body = deleteTodo(parameters['userID'], parameters['todoID'])
    elif function == 'listTodoFiles':
        body = listTodoFiles(parameters['todoID'])
    elif function == 'addTodoFile':
        body = addTodoFile(parameters['todoID'], parameters['fileName'], parameters['fileUrl'])
    elif function == 'deleteTodoFile':
        body = deleteTodoFile(parameters['todoID'], parameters['fileID'])
    else:
        body = {'error': f'{event["actionGroup"]}::{function} is not a valid function'}

    return {
        'response': {
            'actionGroup': event['actionGroup'],
            'function': function,
            'functionResponse': {
                'responseBody': {
                    'TEXT': {'body': json.dumps(body)}
                }
            }
        }
    }
