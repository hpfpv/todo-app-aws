"""
Tests for action_group handler trust boundary.

Verifies:
- userID is read from event['promptSessionAttributes'], not from parameters['userID']
- ownership is enforced: every todoID/fileID access requires the user own the todo
- addTodoFile rejects URLs not on the CDN allowlist
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault('TODO_TABLE', 'test-todo-table')
os.environ.setdefault('FILES_TABLE', 'test-files-table')
os.environ.setdefault('FILES_BUCKET', 'test-bucket')
os.environ.setdefault('FILES_BUCKET_CDN', 'cdn.test.example')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

with patch('boto3.client', return_value=MagicMock()):
    from action_group import handler


def _event(function, parameters=None, prompt_session_attributes=None):
    return {
        'actionGroup': 'TodoActions',
        'function': function,
        'parameters': [{'name': k, 'value': v} for k, v in (parameters or {}).items()],
        'promptSessionAttributes': prompt_session_attributes or {},
    }


def _ddb_todo_item(todo_id='t1', user_id='owner@e.com'):
    return {'Item': {
        'todoID': {'S': todo_id},
        'userID': {'S': user_id},
        'dateCreated': {'S': '2026-05-04'},
        'title': {'S': 'X'},
        'description': {'S': 'X'},
        'notes': {'S': ''},
        'dateDue': {'S': '2026-05-10'},
        'completed': {'BOOL': False},
    }}


class TestAuthoritativeUserId(unittest.TestCase):

    @patch.object(handler, 'client')
    def test_getTodos_uses_session_userid_not_parameter(self, mock_client):
        mock_client.query.return_value = {'Items': []}
        event = _event(
            'getTodos',
            parameters={'userID': 'attacker@e.com'},
            prompt_session_attributes={'userID': 'real@e.com'},
        )
        handler.lambda_handler(event, None)
        call = mock_client.query.call_args
        attr_value = call.kwargs['KeyConditions']['userID']['AttributeValueList'][0]['S']
        self.assertEqual(attr_value, 'real@e.com')

    @patch.object(handler, 'client')
    def test_missing_session_userid_is_rejected(self, mock_client):
        event = _event('getTodos', parameters={'userID': 'attacker@e.com'},
                       prompt_session_attributes={})
        result = handler.lambda_handler(event, None)
        body = json.loads(result['response']['functionResponse']['responseBody']['TEXT']['body'])
        self.assertIn('error', body)


class TestOwnershipEnforcement(unittest.TestCase):

    @patch.object(handler, 'client')
    def test_completeTodo_rejects_other_user_todo(self, mock_client):
        mock_client.get_item.return_value = _ddb_todo_item(user_id='someone-else@e.com')
        event = _event(
            'completeTodo',
            parameters={'todoID': 't1'},
            prompt_session_attributes={'userID': 'attacker@e.com'},
        )
        result = handler.lambda_handler(event, None)
        body = json.loads(result['response']['functionResponse']['responseBody']['TEXT']['body'])
        self.assertIn('error', body)
        # Must NOT have called update_item
        mock_client.update_item.assert_not_called()

    @patch.object(handler, 'client')
    def test_completeTodo_succeeds_when_owner_matches(self, mock_client):
        mock_client.get_item.return_value = _ddb_todo_item(user_id='owner@e.com')
        event = _event(
            'completeTodo',
            parameters={'todoID': 't1'},
            prompt_session_attributes={'userID': 'owner@e.com'},
        )
        handler.lambda_handler(event, None)
        mock_client.update_item.assert_called_once()


class TestAddTodoFileUrlAllowlist(unittest.TestCase):

    @patch.object(handler, 'client')
    def test_rejects_url_outside_cdn(self, mock_client):
        mock_client.get_item.return_value = _ddb_todo_item(user_id='owner@e.com')
        event = _event(
            'addTodoFile',
            parameters={'todoID': 't1', 'fileName': 'a.png', 'fileUrl': 'https://evil.example/a.png'},
            prompt_session_attributes={'userID': 'owner@e.com'},
        )
        result = handler.lambda_handler(event, None)
        body = json.loads(result['response']['functionResponse']['responseBody']['TEXT']['body'])
        self.assertIn('error', body)
        mock_client.put_item.assert_not_called()

    @patch.object(handler, 'client')
    def test_accepts_url_on_cdn(self, mock_client):
        mock_client.get_item.return_value = _ddb_todo_item(user_id='owner@e.com')
        event = _event(
            'addTodoFile',
            parameters={'todoID': 't1', 'fileName': 'a.png', 'fileUrl': 'https://cdn.test.example/a.png'},
            prompt_session_attributes={'userID': 'owner@e.com'},
        )
        handler.lambda_handler(event, None)
        mock_client.put_item.assert_called_once()


if __name__ == '__main__':
    unittest.main()
