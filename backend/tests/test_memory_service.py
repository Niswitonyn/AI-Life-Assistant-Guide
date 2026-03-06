"""
Unit tests for memory service and conversation management
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.memory.memory_service import MemoryService
from app.database.models import ConversationMemory


class TestMemoryService:
    """Test memory service for conversation storage and retrieval"""
    
    def setup_method(self):
        """Setup for each test"""
        self.mock_db = Mock(spec=Session)
    
    def test_save_message_creates_record(self):
        """Should create and save a conversation memory record"""
        service = MemoryService(self.mock_db)
        
        service.save_message(
            user_id="test_user",
            role="user",
            content="hello"
        )
        
        # Verify db.add and db.commit were called
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        
        # Verify the message passed to add
        saved_msg = self.mock_db.add.call_args[0][0]
        assert saved_msg.user_id == "test_user"
        assert saved_msg.role == "user"
        assert saved_msg.content == "hello"
    
    def test_save_assistant_message(self):
        """Should save assistant messages"""
        service = MemoryService(self.mock_db)
        
        service.save_message(
            user_id="test_user",
            role="assistant",
            content="response"
        )
        
        self.mock_db.add.assert_called_once()
        saved_msg = self.mock_db.add.call_args[0][0]
        assert saved_msg.role == "assistant"
        assert saved_msg.content == "response"
    
    def test_get_recent_messages(self):
        """Should retrieve recent messages for a user"""
        # Create mock memory records
        mock_messages = [
            Mock(spec=ConversationMemory, user_id="user1", role="user", content="msg1"),
            Mock(spec=ConversationMemory, user_id="user1", role="assistant", content="response1"),
            Mock(spec=ConversationMemory, user_id="user1", role="user", content="msg2"),
        ]
        
        # Setup mock query chain
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
        
        service = MemoryService(self.mock_db)
        result = service.get_recent_messages("user1", limit=10)
        
        # Verify
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
    
    def test_get_recent_messages_empty(self):
        """Should return empty list if no messages"""
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        service = MemoryService(self.mock_db)
        result = service.get_recent_messages("nonexistent_user", limit=10)
        
        assert result == []
    
    def test_get_recent_messages_respects_limit(self):
        """Should respect the limit parameter"""
        mock_messages = [Mock(spec=ConversationMemory) for _ in range(5)]
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
        
        service = MemoryService(self.mock_db)
        service.get_recent_messages("user1", limit=3)
        
        # Verify limit was called with 3
        limit_call = self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit
        limit_call.assert_called_with(3)
    
    def test_get_recent_messages_filters_by_user(self):
        """Should filter messages by user_id"""
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        service = MemoryService(self.mock_db)
        service.get_recent_messages("specific_user", limit=10)
        
        # Verify ConversationMemory model was queried
        self.mock_db.query.assert_called_once()
        query_arg = self.mock_db.query.call_args[0][0]
        assert query_arg == ConversationMemory
    
    def test_messages_returned_in_correct_order(self):
        """Should return messages in chronological order (oldest first)"""
        # Mock returns messages in DESC order (as DB would with order_by desc)
        mock_messages = [
            Mock(id=3, role="user", content="msg2"),
            Mock(id=2, role="assistant", content="resp1"),
            Mock(id=1, role="user", content="msg1"),
        ]
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
        
        service = MemoryService(self.mock_db)
        result = service.get_recent_messages("user1", limit=10)
        
        # After reversed(), should be chronological (oldest first)
        assert len(result) == 3
        assert result[0]["content"] == "msg1"  # Oldest
        assert result[1]["content"] == "resp1"
        assert result[2]["content"] == "msg2"  # Newest


class TestMultiUserIsolation:
    """Test that messages are properly isolated by user"""
    
    def setup_method(self):
        """Setup for each test"""
        self.mock_db = Mock(spec=Session)
    
    def test_messages_isolated_by_user_id(self):
        """Should not mix messages between users"""
        service = MemoryService(self.mock_db)
        
        service.save_message(user_id="user1", role="user", content="user1 message")
        service.save_message(user_id="user2", role="user", content="user2 message")
        
        # Should have made two separate saves
        assert self.mock_db.add.call_count == 2
        
        # Verify user IDs are different
        calls = self.mock_db.add.call_args_list
        msg1 = calls[0][0][0]
        msg2 = calls[1][0][0]
        
        assert msg1.user_id == "user1"
        assert msg2.user_id == "user2"
    
    def test_get_messages_filters_correct_user(self):
        """Should only return messages for specified user"""
        # Create messages for different users
        user1_msgs = [
            Mock(id=1, user_id="user1", role="user", content="msg1"),
            Mock(id=2, user_id="user1", role="assistant", content="resp1"),
        ]
        
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = user1_msgs
        
        service = MemoryService(self.mock_db)
        result = service.get_recent_messages("user1")
        
        # Should only return user1 messages
        assert len(result) == 2
        assert all(msg["content"] != "user2" for msg in result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
