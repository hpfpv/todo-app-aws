import boto3
import json
import os
import logging
from collections import defaultdict
from boto3.dynamodb.conditions import Key

client = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def getTodosJson(items):
    # loop through the returned todos and add their attributes to a new dict
    # that matches the JSON response structure expected by the frontend.
    todoList = defaultdict(list)

    for item in items:
        todo = {}
        todo["todoID"] = item["todoID"]["S"]
        todo["userID"] = item["userID"]["S"]
        todo["dateCreated"] = item["dateCreated"]["S"]
        todo["title"] = item["title"]["S"]
        todo["description"] = item["description"]["S"]
        todo["dateDue"] = item["dateDue"]["S"]
        todo["completed"] = item["completed"]["BOOL"]
        todoList["todos"].append(todo)
    return todoList
 
def getTodos(userID):
    # Use the DynamoDB API Query to retrieve todos from the table that belong
    # to the specified userID.
    filter = "userID"
    response = client.query(
        TableName=os.environ['TODO_TABLE'],
        IndexName=filter+'Index',
        KeyConditions={
            filter: {
                'AttributeValueList': [
                    {
                        'S': userID
                    }
                ],
                'ComparisonOperator': "EQ"
            }
        }
    )
    logging.info(response["Items"])
    todoList = getTodosJson(response["Items"])
    return json.dumps(todoList)

def lambda_handler(event, context):
    logger.info(event)
    userID = event["pathParameters"]["userID"]
    print(f"Getting all todos for user {userID}")
    items = getTodos(userID)
    logger.info(items)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://mythicalmysfits.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(items)
    }

