import boto3
import json
import os
import logging
from collections import defaultdict
from boto3.dynamodb.conditions import Key

client = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def getFilesJson(items):
    # loop through the returned todos and add their attributes to a new dict
    # that matches the JSON response structure expected by the frontend.
    fileList = defaultdict(list)

    for item in items:
        file = {}
        file["fileID"] = item["fileID"]["S"]
        file["todoID"] = item["todoID"]["S"]
        file["fileName"] = item["fileName"]["S"]
        file["filePath"] = item["filePath"]["S"]
        fileList["files"].append(file)
    return fileList
 
def getTodosFiles(todoID):
    # Use the DynamoDB API Query to retrieve todo files from the table that belong
    # to the specified todoID.
    filter = "todoID"
    response = client.query(
        TableName=os.environ['TODOFILES_TABLE'],
        IndexName=filter+'Index',
        KeyConditions={
            filter: {
                'AttributeValueList': [
                    {
                        'S': todoID
                    }
                ],
                'ComparisonOperator': "EQ"
            }
        }
    )
    logging.info(response["Items"])
    fileList = getFilesJson(response["Items"])
    return json.dumps(fileList)

def lambda_handler(event, context):
    logger.info(event)
    todoID = event["pathParameters"]["todoID"]
    print(f"Getting all files for todo {todoID}")
    items = getTodosFiles(todoID)
    logger.info(items)
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

