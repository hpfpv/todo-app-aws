import boto3
import json
import os
import logging


client = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def completeTodo(todoID):
    response = client.update_item(
        TableName=os.environ['TODO_TABLE'],
        Key={
            'todoID': {
                'S': todoID
            }
        },
        UpdateExpression="SET completed = :b",
        ExpressionAttributeValues={':b': {'BOOL': True}}
    )
    response = {}
    response["Update"] = "Success";

    return json.dumps(response)

def lambda_handler(event, context):
    logger.info(event)
    todoID = event['pathParameters']['todoID']
    logger.info(f'Completed todo: {todoID}')
    response = completeTodo(todoID)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://todo.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Content-Type': 'application/json'
        },
        'body': response
    }