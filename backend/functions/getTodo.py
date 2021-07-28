import boto3
import json
import os
import logging

client = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def getTodoJson(item):
    todo = {}
    todo["todoID"] = item["todoID"]["S"]
    todo["userID"] = item["userID"]["S"]
    todo["dateCreated"] = item["dateCreated"]["S"]
    todo["title"] = item["title"]["S"]
    todo["description"] = item["description"]["S"]
    todo["notes"] = item["notes"]["S"]
    todo["dateDue"] = item["dateDue"]["S"]
    todo["completed"] = item["completed"]["BOOL"]

    return todo

def getTodo(todoID):
    response = client.get_item(
        TableName=os.environ['TODO_TABLE'],
        Key={
            'todoID': {
                'S': todoID
            }
        }
    )
    response = getTodoJson(response["Item"])
    return json.dumps(response)

def lambda_handler(event, context):
    logger.info(event)
    todoID = event['pathParameters']['todoID']
    print(f'Getting todo: {todoID}')
    items = getTodo(todoID)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://todo.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET',
            'Content-Type': 'application/json'
        },
        'body': items
    }