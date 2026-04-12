"""
Tests for websocket_handler._default.

Verifies that:
- input_text sent to Bedrock contains only the human message (no XML prefix)
- sessionState carries userID via promptSessionAttributes
- session_id is read from DynamoDB and reused
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Set env vars before module import (boto3 clients created at module level)
os.environ['BOT_TABLE'] = 'test-bot-table'
os.environ['AGENT_ID'] = 'test-agent-id'
os.environ['AGENT_ALIAS_ID'] = 'test-alias-id'
os.environ['WS_ENDPOINT'] = 'https://test.execute-api.us-east-1.amazonaws.com/production'
os.environ['ENABLE_TRACE'] = 'false'

# Add src to import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

with patch('boto3.client'):
    from websocket_handler import handler


def _agent_response(text: str) -> dict:
    """Build a minimal mock invoke_agent response that the handler can stream."""
    return {'completion': [{'chunk': {'bytes': text.encode('utf-8')}}]}


def _ddb_conn_item(session_id: str = 'sess-001', user_id: str = 'u@e.com') -> dict:
    return {
        'Item': {
            'sessionId': {'S': session_id},
            'userID': {'S': user_id},
            'ttl': {'N': '9999999999'},
        }
    }


class TestDefaultInputText(unittest.TestCase):

    @patch.object(handler, '_api_gw_mgmt')
    @patch.object(handler, 'bedrock_agent_runtime')
    @patch.object(handler, 'dynamodb')
    def test_input_text_is_only_human_message(self, mock_ddb, mock_bedrock, mock_apigw):
        """input_text must be the raw human message — no XML prefix."""
        mock_ddb.get_item.return_value = _ddb_conn_item()
        mock_bedrock.invoke_agent.return_value = _agent_response('OK')

        handler._default('conn-1', 'u@e.com', json.dumps({'human': 'list my todos'}))

        call_kwargs = mock_bedrock.invoke_agent.call_args[1]
        self.assertEqual(call_kwargs['inputText'], 'list my todos')

    @patch.object(handler, '_api_gw_mgmt')
    @patch.object(handler, 'bedrock_agent_runtime')
    @patch.object(handler, 'dynamodb')
    def test_input_text_has_no_xml_userid_tag(self, mock_ddb, mock_bedrock, mock_apigw):
        """No <userid> XML leakage in the message sent to Bedrock."""
        mock_ddb.get_item.return_value = _ddb_conn_item()
        mock_bedrock.invoke_agent.return_value = _agent_response('OK')

        handler._default('conn-1', 'u@e.com', json.dumps({'human': 'hello'}))

        call_kwargs = mock_bedrock.invoke_agent.call_args[1]
        self.assertNotIn('<userid>', call_kwargs['inputText'])
        self.assertNotIn('</userid>', call_kwargs['inputText'])


class TestDefaultSessionAttributes(unittest.TestCase):

    @patch.object(handler, '_api_gw_mgmt')
    @patch.object(handler, 'bedrock_agent_runtime')
    @patch.object(handler, 'dynamodb')
    def test_invoke_agent_has_session_state(self, mock_ddb, mock_bedrock, mock_apigw):
        """invoke_agent must include sessionState."""
        mock_ddb.get_item.return_value = _ddb_conn_item()
        mock_bedrock.invoke_agent.return_value = _agent_response('OK')

        handler._default('conn-1', 'u@e.com', json.dumps({'human': 'hello'}))

        call_kwargs = mock_bedrock.invoke_agent.call_args[1]
        self.assertIn('sessionState', call_kwargs)

    @patch.object(handler, '_api_gw_mgmt')
    @patch.object(handler, 'bedrock_agent_runtime')
    @patch.object(handler, 'dynamodb')
    def test_prompt_session_attributes_contains_user_id(self, mock_ddb, mock_bedrock, mock_apigw):
        """sessionState.promptSessionAttributes must carry the userID."""
        mock_ddb.get_item.return_value = _ddb_conn_item(user_id='alice@example.com')
        mock_bedrock.invoke_agent.return_value = _agent_response('OK')

        handler._default('conn-1', 'alice@example.com', json.dumps({'human': 'hello'}))

        call_kwargs = mock_bedrock.invoke_agent.call_args[1]
        attrs = call_kwargs['sessionState']['promptSessionAttributes']
        self.assertEqual(attrs['userID'], 'alice@example.com')

    @patch.object(handler, '_api_gw_mgmt')
    @patch.object(handler, 'bedrock_agent_runtime')
    @patch.object(handler, 'dynamodb')
    def test_session_id_reused_from_dynamodb(self, mock_ddb, mock_bedrock, mock_apigw):
        """Session ID from DynamoDB must be forwarded to invoke_agent."""
        mock_ddb.get_item.return_value = _ddb_conn_item(session_id='existing-sess-xyz')
        mock_bedrock.invoke_agent.return_value = _agent_response('OK')

        handler._default('conn-1', 'u@e.com', json.dumps({'human': 'hello'}))

        call_kwargs = mock_bedrock.invoke_agent.call_args[1]
        self.assertEqual(call_kwargs['sessionId'], 'existing-sess-xyz')


if __name__ == '__main__':
    unittest.main()
