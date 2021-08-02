import boto3
import json
import os
import logging
from collections import defaultdict
from boto3.dynamodb.conditions import Key
import re

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
        todo["notes"] = item["notes"]["S"]
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
    items = json.dumps(todoList)
    data = json.loads(items)
    response = defaultdict(list)
    sortedData1 = sorted(data["todos"], key = lambda i: i["dateCreated"], reverse=True)
    sortedData2 = sorted(sortedData1, key = lambda i: i["dateDue"])
    sortedData3 = sorted(sortedData2, key = lambda i: i["completed"])
    response = defaultdict(list)

    for item in sortedData3:
        todo = {}
        todo["todoID"] = item["todoID"]
        todo["userID"] = item["userID"]
        todo["dateCreated"] = item["dateCreated"]
        todo["title"] = item ["title"]
        todo["description"] = item["description"]
        todo["notes"] = item["notes"]
        todo["dateDue"] = item["dateDue"]
        todo["completed"] = item["completed"]

        response["todos"].append(todo)
    logger.info(response)
    return response

def getSearchedTodos(userID, filter):
    items = getTodos(userID)
    data = items
    response = defaultdict(list)
    
    for item in data["todos"]:
        todo = {}
        if re.search(filter, item["title"], re.IGNORECASE): 
            todo["todoID"] = item["todoID"]
            todo["userID"] = item["userID"]
            todo["dateCreated"] = item["dateCreated"]
            todo["title"] = item ["title"]
            todo["description"] = item["description"]
            todo["notes"] = item["notes"]
            todo["dateDue"] = item["dateDue"]
            todo["completed"] = item["completed"]
            response["todos"].append(todo)
    
    logging.info(response)
    return response

def lambda_handler(event, context):
    logger.info(event)
    userID = event["pathParameters"]["userID"]
    if (event["rawQueryString"] == ''):
        print(f"Getting all todos for user {userID}")
        response = getTodos(userID)
        logger.info(response)
    else:
        print(f"Getting filtered for user {userID}")
        filter = event["queryStringParameters"]["search"]
        response = getSearchedTodos(userID, filter)
        logger.info(response)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://todo.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response)
    }

