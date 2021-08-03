import boto3
import json
import os
import logging
import uuid
from botocore.exceptions import ClientError

dynamo = boto3.client('dynamodb', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

bucket = os.environ['TODOFILES_BUCKET']
bucketCDN = os.environ['TODOFILES_BUCKET_CDN']

def lambda_handler(event, context):
    logger.info(event)
    eventBody = json.loads(event["body"])
    todoID = event["pathParameters"]["todoID"]
    fileName = eventBody["fileName"]
    fileID = str(uuid.uuid4())
    filePath = eventBody["filePath"]
    fileKey = str(filePath).replace(f'https://{bucket}/.s3.amazonaws.com/','')
    filePathCDN = 'https://' + bucketCDN + '/' + filePath
    fileForDynamo = {}
    fileForDynamo["fileID"] =  {
        "S": fileID
    }
    fileForDynamo["todoID"] =  {
        "S": todoID
    }
    fileForDynamo["fileName"] =  {
        "S": fileName
    }
    fileForDynamo["filePath"] =  {
        "S": filePathCDN
    }

    logger.info(fileForDynamo)
    try:
        responseDB = dynamo.put_item(
        TableName=os.environ['TODOFILES_TABLE'],
        Item=fileForDynamo
        ) 

        logger.info(responseDB)
    except ClientError as err:
        logger.info(err)
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