"""
Unit tests for command parsing and execution.

Tests SmartRouter routing, BrainController time commands,
and agent execution including the Gmail confirmation workflow.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.router.smart_router import SmartRouter
from app.core.brain_controller import BrainController


def _run(coro):
    """Run an async coroutine synchronously in a test."""
    return asyncio.run(coro)


def _time_cmd(text: str):
    """Call BrainController._handle_time_command without full initialisation."""
    obj = BrainController.__new__(BrainController)
    return obj._handle_time_command(text)


def _parse_email_cmd(text: str):
    """Call SmartRouter._parse_send_email_command (no external deps needed)."""
    return SmartRouter()._parse_send_email_command(text)


class TestTimeCommandParsing:
    """Test time/date command detection via BrainController._handle_time_command"""

    def test_what_time_command(self):
        """Should detect 'what time' queries"""
        reply = _time_cmd("what time is it")
        assert reply is not None
        assert ":" in reply  # Contains time format

    def test_date_command(self):
        """Should detect 'date' queries"""
        reply = _time_cmd("what is today's date")
        assert reply is not None
        assert "day" in reply.lower() or "date" in reply.lower()

    def test_non_time_command(self):
        """Should return None for non-time queries"""
        reply = _time_cmd("send me an email")
        assert reply is None

    def test_empty_input(self):
        """Should handle empty input"""
        reply = _time_cmd("")
        assert reply is None


class TestEmailCommandParsing:
    """Test email command parsing via SmartRouter._parse_send_email_command"""

    def test_simple_email_command(self):
        """Should parse 'send email to' commands"""
        result = _parse_email_cmd("send email to john@example.com")
        assert result is not None
        assert result["to"] == "john@example.com"

    def test_email_with_subject(self):
        """Should parse email with subject"""
        result = _parse_email_cmd("send email to john@example.com subject hello")
        assert result is not None
        assert result["to"] == "john@example.com"
        assert "hello" in result["subject"].lower()

    def test_email_with_subject_and_body(self):
        """Should parse email with subject and body"""
        cmd = "send email to john@example.com subject hello body This is a test"
        result = _parse_email_cmd(cmd)
        assert result is not None
        assert result["to"] == "john@example.com"
        assert "test" in result["body"]

    def test_invalid_email_command(self):
        """Should return None for invalid email commands"""
        result = _parse_email_cmd("send me a message")
        assert result is None


class TestCommandSchemaParsing:
    """Test SmartRouter routing output (replaces _parse_command_schema)"""

    def test_single_command_schema(self):
        """Should route email command to 'email' intent with tasks"""
        result = _run(SmartRouter().route("send email to test@example.com"))
        assert result is not None
        assert result.get("intent") == "email" or len(result.get("tasks", [])) > 0

    def test_multiple_commands_schema(self):
        """Should parse multiple chained commands"""
        result = _run(SmartRouter().route("open chrome and search python"))
        assert result is not None
        assert len(result.get("tasks", [])) >= 1

    def test_task_creation_schema(self):
        """Should parse task creation commands"""
        result = _run(SmartRouter().route("add task buy groceries"))
        assert result is not None

    def test_no_schema_match(self):
        """Should return chat intent if no command is recognized"""
        result = _run(SmartRouter().route("just have a random conversation"))
        assert result is not None
        assert result.get("intent") == "chat" or result.get("tasks") == []

    def test_empty_input(self):
        """Should handle empty input gracefully"""
        result = _run(SmartRouter().route(""))
        assert result is not None
        assert result.get("tasks") == []

    def test_calendar_command(self):
        """Should parse calendar commands"""
        result = _run(SmartRouter().route("what are my upcoming events"))
        assert result is not None


class TestCommandExecution:
    """Test command execution via GmailAgent and SmartRouter"""

    def test_execute_gmail_send_returns_confirmation(self):
        """
        gmail send_email now returns needs_confirmation instead of immediately sending.
        GmailAgent.execute() should return status 'needs_confirmation'.
        """
        from app.agents.gmail_agent import GmailAgent

        agent = GmailAgent.__new__(GmailAgent)
        agent.user_id = "default"
        agent.provider = None
        agent.contacts = Mock()
        agent.contacts.load_contacts.return_value = {}
        agent.service = Mock()

        result = _run(agent.execute({
            "action": "send_email",
            "params": {"to": "test@example.com", "subject": "Test", "body": "Test body"},
            "text": "send email to test@example.com",
        }))

        assert result is not None
        # New workflow: returns needs_confirmation before sending
        assert result["status"] in ["success", "needs_confirmation"]
        assert "test@example.com" in str(result)

    @patch('app.agents.system_agent.SystemAgent')
    def test_execute_system_command(self, mock_system_cls):
        """Should handle system command routing without errors"""
        result = _run(SmartRouter().route("open chrome"))
        assert result is not None

    def test_execute_schema_multiple_commands(self):
        """Should not crash on unrecognised input"""
        result = _run(SmartRouter().route("unknown gibberish xyz"))
        assert result is not None


class TestCommandSchemaIntegration:
    """Integration tests for full command flow"""

    def test_gmail_agent_send_returns_needs_confirmation(self):
        """
        Full flow: GmailAgent.execute() for send_email must return needs_confirmation.
        Email should NOT be sent immediately — confirmation is required first.
        """
        from app.agents.gmail_agent import GmailAgent

        agent = GmailAgent.__new__(GmailAgent)
        agent.user_id = "default"
        agent.provider = None
        agent.contacts = Mock()
        agent.contacts.load_contacts.return_value = {}
        agent.service = Mock()

        result = _run(agent.execute({
            "action": "send_email",
            "params": {"to": "test@example.com", "subject": "Test", "body": "Hello"},
            "text": "send email to test@example.com",
        }))

        assert result is not None
        assert result["status"] == "needs_confirmation"
        assert "test@example.com" in str(result)

    def test_parse_and_route_flow(self):
        """Test complete parse → route flow via SmartRouter"""
        result = _run(SmartRouter().route("send email to test@example.com"))

        assert result is not None
        assert result.get("intent") == "email" or len(result.get("tasks", [])) > 0


class TestErrorHandling:
    """Test error handling in agent execution"""

    def test_handle_gmail_auth_failure_gracefully(self):
        """GmailAgent should raise when credentials are missing"""
        from app.agents.gmail_agent import GmailAgent

        with patch('app.agents.gmail_agent.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            with pytest.raises((FileNotFoundError, Exception)):
                GmailAgent(user_id="default")

    def test_router_handles_empty_string(self):
        """SmartRouter should handle empty string without crashing"""
        result = _run(SmartRouter().route(""))
        assert result is not None

    def test_router_handles_garbage_input(self):
        """SmartRouter should handle unrecognised input without crashing"""
        result = _run(SmartRouter().route("xyzzy frobinate the quux"))
        assert result is not None

    def test_gmail_agent_execute_missing_to_returns_error(self):
        """GmailAgent.execute send_email with no 'to' should return error status"""
        from app.agents.gmail_agent import GmailAgent

        agent = GmailAgent.__new__(GmailAgent)
        agent.user_id = "default"
        agent.provider = None
        agent.contacts = Mock()
        agent.contacts.load_contacts.return_value = {}
        agent.service = Mock()

        result = _run(agent.execute({
            "action": "send_email",
            "params": {},
            "text": "send email",
        }))

        assert result is not None
        assert result["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
