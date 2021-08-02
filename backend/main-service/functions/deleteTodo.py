import boto3
import json
import os
import logging

dynamo = boto3.client('dynamodb', region_name='us-east-1')
s3 = boto3.resource('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

bucket = s3.Bucket(os.environ['TODOFILES_BUCKET'])

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
    for key in bucket.objects.filter(prefix=prefix):
        key.delete()
        logging.info(f"{key} deleted")
    return (f"{todoID} files deleted from s3")

def deleteTodoFilesDynamo(todoID):
    "foobar"

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
