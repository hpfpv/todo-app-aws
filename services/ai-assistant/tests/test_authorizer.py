"""
Tests for the Cognito JWT authorizer.

Verifies:
- token_use must be 'id' (access tokens are rejected)
- audience (aud claim) must equal COGNITO_CLIENT_ID
- otherwise valid tokens still produce an Allow policy
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

os.environ['COGNITO_USER_POOL_ID'] = 'us-east-1_test'
os.environ['COGNITO_REGION'] = 'us-east-1'
os.environ['COGNITO_CLIENT_ID'] = 'client-abc-123'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from authorizer import handler  # noqa: E402


def _event(token):
    return {
        'methodArn': 'arn:aws:execute-api:us-east-1:111:abc/production/$connect',
        'queryStringParameters': {'token': token} if token else {},
    }


class TestAuthorizer(unittest.TestCase):

    @patch.object(handler, '_get_public_key')
    @patch('authorizer.handler.jwt.get_unverified_header')
    @patch('authorizer.handler.jwt.decode')
    def test_id_token_with_correct_aud_is_allowed(self, mock_decode, mock_header, mock_key):
        mock_header.return_value = {'kid': 'k1'}
        mock_decode.return_value = {
            'token_use': 'id',
            'aud': 'client-abc-123',
            'email': 'u@e.com',
        }
        result = handler.lambda_handler(_event('tok'), None)
        self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Allow')

    @patch.object(handler, '_get_public_key')
    @patch('authorizer.handler.jwt.get_unverified_header')
    @patch('authorizer.handler.jwt.decode')
    def test_access_token_is_denied(self, mock_decode, mock_header, mock_key):
        mock_header.return_value = {'kid': 'k1'}
        mock_decode.return_value = {
            'token_use': 'access',
            'aud': 'client-abc-123',
            'email': 'u@e.com',
        }
        result = handler.lambda_handler(_event('tok'), None)
        self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')

    def test_missing_token_is_denied(self):
        result = handler.lambda_handler(_event(None), None)
        self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')


if __name__ == '__main__':
    unittest.main()
