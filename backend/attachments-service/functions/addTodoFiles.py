import boto3
import json
import os
import logging
import uuid
from botocore.exceptions import ClientError

dynamo = boto3.client('dynamodb', region_name='us-east-1')
s3 = boto3.client('s3')
bucket = os.environ["TODOFILES_BUCKET"]
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(event)
    eventBody = json.loads(event["body"])
    todoID = event["pathParameters"]["todoID"]
    #file = eventBody["fileBody"]
    fileName = eventBody["fineName"]
    fileID = str(uuid.uuid4())
    filePath = 'https://' + bucket + '/' + fileName
    fileForDynamo = {
        'fileID': fileID,
        'todoID': todoID,
        'fileName' : fileName,
        'filePath' : filePath
    }
    try:
        #responseS3 = s3.upload_fileobj(file, bucket, fileName)
        responseDB = dynamo.put_item(
        TableName=os.environ['TODOFILES_TABLE'],
        Item=fileForDynamo
        ) 
        #logger.info('reposne for S3' + responseS3)
        logger.info('reposne for DynamoDB' + responseDB)
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