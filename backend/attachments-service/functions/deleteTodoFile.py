import boto3
import json
import os
import logging
from collections import defaultdict
from boto3.dynamodb.conditions import Key

dynamo = boto3.client('dynamodb', region_name='us-east-1')
s3 = boto3.client('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
bucket = os.environ['TODOFILES_BUCKET']
bucketCDN = os.environ['TODOFILES_BUCKET_CDN']

def deleteTodosFileS3(key):
    response = s3.delete_object(
        Bucket=bucket,
        Key=key,
    )
    logging.info(f"{key} deleted from S3")
    return response
   
def deleteTodosFileDynamo(fileID):
    response = dynamo.delete_item(
        TableName=os.environ['TODOFILES_TABLE'],
        Key={
            'fileID': {
                'S': fileID
            }
        }
    )
    logging.info(f"{fileID} deleted from DynamoDB")
    return response
def lambda_handler(event, context):
    logger.info(event)
    eventBody = json.loads(event["body"])
    fileID = event["pathParameters"]["fileID"]
    filePath = eventBody["filePath"]
    fileKey = str(filePath).replace(f'https://{bucketCDN}/', '').replace('%40','@')
    todoID = event["pathParameters"]["todoID"]

    print(f"deleting file {fileID}")
    deleteTodosFileS3(fileKey)
    deleteTodosFileDynamo(fileID)

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