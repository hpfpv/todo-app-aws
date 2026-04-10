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
