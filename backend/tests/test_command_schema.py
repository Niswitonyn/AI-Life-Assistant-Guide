"""
Unit tests for command schema parsing and execution from routes_ai.py

Tests the unified command executor pattern that should be used by both chat and voice.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

# Import the functions to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api.routes_ai import (
    _parse_command_schema,
    _execute_single_action,
    _execute_command_schema,
    _handle_time_command,
    _parse_send_email_command,
)


class TestTimeCommandParsing:
    """Test time/date command detection"""
    
    def test_what_time_command(self):
        """Should detect 'what time' queries"""
        reply = _handle_time_command("what time is it")
        assert reply is not None
        assert ":" in reply  # Contains time format
    
    def test_date_command(self):
        """Should detect 'date' queries"""
        reply = _handle_time_command("what is today's date")
        assert reply is not None
        assert "day" in reply.lower() or "date" in reply.lower()
    
    def test_non_time_command(self):
        """Should return None for non-time queries"""
        reply = _handle_time_command("send me an email")
        assert reply is None
    
    def test_empty_input(self):
        """Should handle empty input"""
        reply = _handle_time_command("")
        assert reply is None


class TestEmailCommandParsing:
    """Test email command parsing"""
    
    def test_simple_email_command(self):
        """Should parse 'send email to' commands"""
        result = _parse_send_email_command("send email to john@example.com")
        assert result is not None
        assert result["to"] == "john@example.com"
    
    def test_email_with_subject(self):
        """Should parse email with subject"""
        result = _parse_send_email_command("send email to john@example.com subject hello")
        assert result is not None
        assert result["to"] == "john@example.com"
        assert "hello" in result["subject"].lower()
    
    def test_email_with_subject_and_body(self):
        """Should parse email with subject and body"""
        cmd = "send email to john@example.com subject hello body This is a test"
        result = _parse_send_email_command(cmd)
        assert result is not None
        assert result["to"] == "john@example.com"
        assert "test" in result["body"]
    
    def test_invalid_email_command(self):
        """Should return None for invalid email commands"""
        result = _parse_send_email_command("send me a message")
        assert result is None


class TestCommandSchemaParsing:
    """Test complete command schema parsing"""
    
    def test_single_command_schema(self):
        """Should parse single command into schema"""
        result = _parse_command_schema("send email to test@example.com")
        assert result is not None
        assert result["schema"] == "phase3.command.v1"
        assert len(result["commands"]) > 0
        assert result["commands"][0]["action"] == "gmail_send"
    
    def test_multiple_commands_schema(self):
        """Should parse multiple chained commands"""
        result = _parse_command_schema("open chrome and search python")
        assert result is not None
        assert len(result["commands"]) >= 1
    
    def test_task_creation_schema(self):
        """Should parse task creation commands"""
        result = _parse_command_schema("add task buy groceries")
        assert result is not None
        if result:  # May return None if parsing fails
            assert any(cmd["action"] == "task_create" for cmd in result.get("commands", []))
    
    def test_no_schema_match(self):
        """Should return None if no command is recognized"""
        result = _parse_command_schema("just have a random conversation")
        assert result is None or result.get("commands") == []
    
    def test_empty_input(self):
        """Should handle empty input gracefully"""
        result = _parse_command_schema("")
        assert result is None
    
    def test_calendar_command(self):
        """Should parse calendar commands"""
        result = _parse_command_schema("what are my upcoming events")
        assert result is not None


class TestCommandExecution:
    """Test command execution"""
    
    @patch('app.api.routes_ai.GmailAgent')
    def test_execute_gmail_send(self, mock_gmail_agent):
        """Should execute email send action"""
        # Setup mock
        mock_agent_instance = Mock()
        mock_agent_instance.send_email.return_value = "Email sent"
        mock_gmail_agent.return_value = mock_agent_instance
        
        # Mock database
        mock_db = Mock(spec=Session)
        
        # Execute
        result = _execute_single_action(
            "gmail_send",
            {"to": "test@example.com", "subject": "Test", "body": "Test body"},
            "default",
            mock_db
        )
        
        # Assert
        assert result is not None
        assert "test@example.com" in result
        mock_agent_instance.send_email.assert_called_once()
    
    @patch('app.api.routes_ai.SystemAgent')
    def test_execute_system_command(self, mock_system_agent):
        """Should execute system commands"""
        mock_agent_instance = Mock()
        mock_agent_instance.execute.return_value = "System command executed"
        mock_system_agent.return_value = mock_agent_instance
        
        mock_db = Mock(spec=Session)
        
        result = _execute_single_action(
            "system_execute",
            {"command": "shutdown"},
            "default",
            mock_db
        )
        
        assert result is not None
        mock_agent_instance.execute.assert_called_once()
    
    def test_execute_schema_multiple_commands(self):
        """Should execute and combine results from multiple commands"""
        schema = {
            "schema": "phase3.command.v1",
            "commands": [
                {"action": "unknown", "params": {}}  # Will fail gracefully
            ]
        }
        
        mock_db = Mock(spec=Session)
        
        # Should not crash on unknown action
        result = _execute_command_schema(schema, "default", mock_db)
        # Result can be None or string, depending on implementation


class TestCommandSchemaIntegration:
    """Integration tests for full command flow"""
    
    @patch('app.api.routes_ai.GmailAgent')
    @patch('app.api.routes_ai.SystemAgent')
    def test_parse_and_execute_flow(self, mock_system, mock_gmail):
        """Test complete parse → execute flow"""
        # Setup mocks
        mock_gmail_instance = Mock()
        mock_gmail_instance.send_email.return_value = "Email sent"
        mock_gmail.return_value = mock_gmail_instance
        
        # Parse command
        user_input = "send email to test@example.com"
        schema = _parse_command_schema(user_input)
        
        # Verify schema
        assert schema is not None
        assert schema["schema"] == "phase3.command.v1"
        
        # Execute schema
        mock_db = Mock(spec=Session)
        result = _execute_command_schema(schema, "default", mock_db)
        
        # Verify execution
        assert result is not None


class TestErrorHandling:
    """Test error handling in command execution"""
    
    @patch('app.api.routes_ai.GmailAgent')
    def test_handle_gmail_failure_gracefully(self, mock_gmail_agent):
        """Should handle Gmail agent failures without crashing"""
        mock_gmail_agent.side_effect = Exception("Gmail auth failed")
        
        mock_db = Mock(spec=Session)
        
        # Should return error message, not crash
        result = _execute_single_action(
            "gmail_send",
            {"to": "test@example.com", "subject": "Test", "body": "Test"},
            "default",
            mock_db
        )
        
        assert result is not None
        assert "could not access" in result.lower() or "failed" in result.lower()
    
    @patch('app.api.routes_ai.SystemAgent')
    def test_handle_system_command_failure(self, mock_system_agent):
        """Should handle system command failures gracefully"""
        mock_agent_instance = Mock()
        mock_agent_instance.execute.side_effect = Exception("System command failed")
        mock_system_agent.return_value = mock_agent_instance
        
        mock_db = Mock(spec=Session)
        
        result = _execute_single_action(
            "system_execute",
            {"command": "shutdown"},
            "default",
            mock_db
        )
        
        # Should return error message
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
