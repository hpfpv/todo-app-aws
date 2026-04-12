"""
Tests for action_group._clean_user_id.

This function is now a defensive fallback — the primary mechanism is
promptSessionAttributes. Tests verify it strips XML tags correctly in
all edge cases.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Set env vars and patch boto3 before import to prevent real AWS calls
os.environ.setdefault('TODO_TABLE', 'test-todo-table')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

with patch('boto3.client', return_value=MagicMock()):
    from action_group.handler import _clean_user_id


class TestCleanUserId(unittest.TestCase):

    def test_strips_lowercase_tags(self):
        self.assertEqual(_clean_user_id('<userid>foo@bar.com</userid>'), 'foo@bar.com')

    def test_strips_uppercase_tags(self):
        self.assertEqual(_clean_user_id('<USERID>foo@bar.com</USERID>'), 'foo@bar.com')

    def test_strips_mixed_case_tags(self):
        self.assertEqual(_clean_user_id('<UserID>foo@bar.com</UserID>'), 'foo@bar.com')

    def test_passthrough_when_no_tags(self):
        self.assertEqual(_clean_user_id('foo@bar.com'), 'foo@bar.com')

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(_clean_user_id('  foo@bar.com  '), 'foo@bar.com')

    def test_strips_whitespace_inside_tags(self):
        self.assertEqual(_clean_user_id('<userid>  foo@bar.com  </userid>'), 'foo@bar.com')


if __name__ == '__main__':
    unittest.main()
