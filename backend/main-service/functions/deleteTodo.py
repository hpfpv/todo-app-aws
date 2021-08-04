import boto3
import json
import os
import logging
from collections import defaultdict

dynamo = boto3.client('dynamodb', region_name='us-east-1')
s3 = boto3.resource('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

bucket = s3.Bucket(os.environ['TODOFILES_BUCKET'])

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
    response = dynamo.query(
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


def deleteTodo(todoID):
    response = dynamo.delete_item(
        TableName=os.environ['TODO_TABLE'],
        Key={
            'todoID': {
                'S': todoID
            }
        }
    )
    logging.info(f"{todoID} deleted")
    return response

def deleteTodoFilesS3(userID, todoID):
    prefix = userID + "/" + todoID + "/"
    for key in bucket.objects.filter(Prefix=prefix):
        key.delete()
        logging.info(f"{key} deleted")
    return (f"{todoID} files deleted from s3")

def deleteTodoFilesDynamo(todoID):
    data = json.loads(getTodosFiles(todoID))
    if data :
        files = data["files"]
        for file in files:
            fileID = file["fileID"]
            dynamo.delete_item(
                TableName=os.environ['TODOFILES_TABLE'],
                Key={
                    'fileID': {
                        'S': fileID
                    }
                }
            )
            logging.info(f"{fileID} deleted")
        return (f"{todoID} files deleted from dynamoDB")
    else:
        logging.info(f"{todoID}: no files to delete")
        return (f"{todoID}: no files to delete")


def lambda_handler(event, context):
    logger.info(event)
    todoID = event["pathParameters"]["todoID"]
    userID = event["pathParameters"]["userID"]

    print(f"deleting todo {todoID}")
    deleteTodoFilesS3(userID, todoID)
    deleteTodoFilesDynamo(todoID)
    deleteTodo(todoID)

    responseBody = {}
    responseBody["status"] = "success"
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': 'https://todo.houessou.com',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET, DELETE, POST',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(responseBody)  
    }
