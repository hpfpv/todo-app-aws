import boto3
import json
import os
import logging
import uuid
from datetime import datetime

client = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
dateTimeObj = datetime.now()

def lambda_handler(event, context):
    logger.info(event)
    eventBody = json.loads(event["body"])
    userID = event["pathParameters"]["userID"]
    todo = {}
    todo["todoID"] = {
        "S": str(uuid.uuid4())
        }
    todo["userID"] = {
        "S": userID
        }
    todo["dateCreated"] = {
        "S": str(dateTimeObj)
        }
    todo["title"] = {
        "S": eventBody["title"]
        }    
    todo["description"] = {
        "S": eventBody["description"]
        }
    todo["notes"] = {
        "S": ""
        }
    todo["dateDue"] = {
        "S": eventBody["dateDue"]
        }
    todo["completed"] = {
        "BOOL": False
        }

    response = client.put_item(
        TableName=os.environ['TODO_TABLE'],
        Item=todo
        ) 
    logger.info(response)   
    responseBody = {}
    responseBody["status"] = "success"
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://todo.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(responseBody)  
    }