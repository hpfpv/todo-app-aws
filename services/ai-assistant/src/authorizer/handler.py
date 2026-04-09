import json
import os
import time
import urllib.request
import logging
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_JWKS_CACHE = None
_JWKS_CACHE_TIME = 0
_JWKS_TTL = 3600  # seconds


def _get_jwks():
    global _JWKS_CACHE, _JWKS_CACHE_TIME
    now = time.time()
    if _JWKS_CACHE and (now - _JWKS_CACHE_TIME) < _JWKS_TTL:
        return _JWKS_CACHE
    pool_id = os.environ['COGNITO_USER_POOL_ID']
    region = os.environ['COGNITO_REGION']
    url = (
        f'https://cognito-idp.{region}.amazonaws.com'
        f'/{pool_id}/.well-known/jwks.json'
    )
    with urllib.request.urlopen(url, timeout=5) as resp:
        _JWKS_CACHE = json.loads(resp.read())
    _JWKS_CACHE_TIME = now
    return _JWKS_CACHE


def _get_public_key(kid):
    jwks = _get_jwks()
    for key in jwks['keys']:
        if key['kid'] == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))
    raise ValueError(f'Key {kid} not found in JWKS')


def _policy(principal_id, effect, resource, context=None):
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource,
            }],
        },
    }
    if context:
        policy['context'] = context
    return policy


def lambda_handler(event, context):
    method_arn = event['methodArn']
    token = (event.get('queryStringParameters') or {}).get('token')

    if not token:
        logger.info(json.dumps({'level': 'INFO', 'result': 'Deny', 'reason': 'no token'}))
        return _policy('anonymous', 'Deny', method_arn)

    try:
        header = jwt.get_unverified_header(token)
        public_key = _get_public_key(header['kid'])
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={'verify_aud': False},
        )
        user_id = payload.get('email') or payload.get('cognito:username', 'unknown')
        logger.info(json.dumps({
            'level': 'INFO',
            'result': 'Allow',
            'userIdPrefix': user_id[:3] + '***',
        }))
        return _policy(user_id, 'Allow', method_arn, {'userID': user_id})
    except Exception as exc:
        logger.error(json.dumps({'level': 'ERROR', 'result': 'Deny', 'reason': str(exc)}))
        return _policy('anonymous', 'Deny', method_arn)
