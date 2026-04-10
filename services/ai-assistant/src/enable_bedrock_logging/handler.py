import json
import logging
import os
import urllib.request

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client('bedrock', region_name='us-east-1')


def _send_cfn_response(event, context, status, data=None):
    body = json.dumps({
        'Status': status,
        'Reason': f'See CloudWatch: {context.log_stream_name}',
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {},
    })
    req = urllib.request.Request(
        url=event['ResponseURL'],
        data=body.encode(),
        method='PUT',
        headers={'Content-Type': ''},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.info(json.dumps({'cfn_response_status': resp.status}))


def lambda_handler(event, context):
    logger.info(json.dumps({'RequestType': event.get('RequestType')}))
    try:
        if event['RequestType'] in ('Create', 'Update'):
            bedrock.put_model_invocation_logging_configuration(
                loggingConfig={
                    'cloudWatchConfig': {
                        'logGroupName': '/aws/bedrock/model-invocations',
                        'roleArn': os.environ['LOGGING_ROLE_ARN'],
                    },
                    'textDataDeliveryEnabled': True,
                    'imageDataDeliveryEnabled': False,
                    'embeddingDataDeliveryEnabled': False,
                }
            )
            logger.info(json.dumps({'level': 'INFO', 'action': 'bedrock_logging_enabled'}))
        _send_cfn_response(event, context, 'SUCCESS')
    except Exception as exc:
        logger.error(json.dumps({'level': 'ERROR', 'error': str(exc)}))
        _send_cfn_response(event, context, 'FAILED', {'Error': str(exc)})
