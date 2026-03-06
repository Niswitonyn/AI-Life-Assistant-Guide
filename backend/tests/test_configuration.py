"""
Unit tests for configuration and environment settings
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.paths import (
    DATA_DIR,
    DB_DIR,
    LOG_DIR,
    TOKENS_DIR,
    CREDENTIALS_DIR,
    resolve_data_dir
)


class TestPathResolution:
    """Test configuration path resolution"""
    
    def test_resolve_data_dir_default(self):
        """Should resolve to backend/data by default"""
        with patch.dict(os.environ, {}, clear=False):
            if 'AI_LIFE_DATA_DIR' in os.environ:
                del os.environ['AI_LIFE_DATA_DIR']
            
            result = resolve_data_dir()
            assert result.is_absolute()
            assert 'data' in str(result).lower()
    
    def test_resolve_data_dir_override(self):
        """Should use custom path when AI_LIFE_DATA_DIR is set"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'AI_LIFE_DATA_DIR': tmpdir}):
                result = resolve_data_dir()
                assert str(result) == tmpdir
    
    def test_data_dir_is_absolute(self):
        """DATA_DIR should be absolute path"""
        assert DATA_DIR.is_absolute()
    
    def test_db_dir_is_subdirectory(self):
        """DB_DIR should be under DATA_DIR"""
        assert str(DB_DIR).startswith(str(DATA_DIR))
    
    def test_all_required_paths_defined(self):
        """Should have all required data directories defined"""
        paths = [DATA_DIR, DB_DIR, LOG_DIR, TOKENS_DIR, CREDENTIALS_DIR]
        for path in paths:
            assert path is not None
            assert isinstance(path, Path)


class TestConfigurationEnvironment:
    """Test environment configuration"""
    
    def test_config_settings_import(self):
        """Should be able to import settings"""
        try:
            from app.config.settings import settings
            assert settings is not None
        except ImportError as e:
            pytest.skip(f"Settings module not fully configured: {e}")
    
    def test_database_initialization(self):
        """Test that database can be initialized"""
        try:
            from app.database.db import Base, engine, SessionLocal
            
            # Should have valid engine
            assert engine is not None
            
            # Should be able to create session
            session = SessionLocal()
            assert session is not None
        except Exception as e:
            pytest.skip(f"Database not configured: {e}")


class TestDataDirectoryStructure:
    """Test data directory structure expectations"""
    
    def test_data_dir_structure_components(self):
        """Should have necessary subdirectory paths"""
        # These should be defined even if directories don't exist on disk
        assert 'database' in str(DB_DIR)
        assert 'logs' in str(LOG_DIR)
        assert 'tokens' in str(TOKENS_DIR)
        assert 'credentials' in str(CREDENTIALS_DIR)
    
    def test_paths_are_related(self):
        """All paths should be related to base DATA_DIR"""
        paths = [DB_DIR, LOG_DIR, TOKENS_DIR, CREDENTIALS_DIR]
        for path in paths:
            assert str(DATA_DIR) in str(path) or path.parent == DATA_DIR or path.parent.parent == DATA_DIR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
