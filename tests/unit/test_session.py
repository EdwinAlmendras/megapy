"""
Unit tests for session management.

Tests SQLiteSession, MemorySession, and SessionData.
"""
import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from megapy.core.session import (
    SessionStorage,
    SessionData,
    SQLiteSession,
    MemorySession
)


class TestSessionData:
    """Tests for SessionData model."""
    
    def test_create_session_data(self):
        """Test creating session data."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test User",
            master_key=b'\x00' * 16
        )
        
        assert data.email == "test@example.com"
        assert data.session_id == "sid123"
        assert data.user_id == "uid456"
        assert data.user_name == "Test User"
        assert len(data.master_key) == 16
    
    def test_session_data_to_dict(self):
        """Test converting to dictionary."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test User",
            master_key=b'\x01\x02\x03' + b'\x00' * 13
        )
        
        result = data.to_dict()
        
        assert result['email'] == "test@example.com"
        assert result['session_id'] == "sid123"
        assert result['master_key'] == "01020300000000000000000000000000"
        assert 'created_at' in result
        assert 'updated_at' in result
    
    def test_session_data_from_dict(self):
        """Test creating from dictionary."""
        dict_data = {
            'email': 'test@example.com',
            'session_id': 'sid123',
            'user_id': 'uid456',
            'user_name': 'Test User',
            'master_key': '00' * 16,
            'private_key': None,
            'rsa_private_key_data': None,
            'created_at': '2024-01-01T12:00:00',
            'updated_at': '2024-01-01T12:00:00'
        }
        
        data = SessionData.from_dict(dict_data)
        
        assert data.email == "test@example.com"
        assert data.session_id == "sid123"
        assert len(data.master_key) == 16
    
    def test_session_data_to_json(self):
        """Test JSON serialization."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test User",
            master_key=b'\x00' * 16
        )
        
        json_str = data.to_json()
        
        assert '"email": "test@example.com"' in json_str
        assert '"session_id": "sid123"' in json_str
    
    def test_session_data_from_json(self):
        """Test JSON deserialization."""
        json_str = '{"email": "test@example.com", "session_id": "sid123", "user_id": "uid456", "user_name": "Test", "master_key": "00000000000000000000000000000000", "private_key": null, "rsa_private_key_data": null, "created_at": "2024-01-01T12:00:00", "updated_at": "2024-01-01T12:00:00"}'
        
        data = SessionData.from_json(json_str)
        
        assert data.email == "test@example.com"
        assert data.session_id == "sid123"
    
    def test_is_valid(self):
        """Test validation."""
        valid_data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        
        assert valid_data.is_valid() is True
        
        # Invalid: empty email
        invalid_data = SessionData(
            email="",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        assert invalid_data.is_valid() is False
        
        # Invalid: wrong key length
        invalid_key = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 8  # Wrong length
        )
        assert invalid_key.is_valid() is False
    
    def test_update_timestamp(self):
        """Test timestamp update."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        
        old_time = data.updated_at
        data.update_timestamp()
        
        assert data.updated_at >= old_time


class TestMemorySession:
    """Tests for MemorySession storage."""
    
    def test_implements_protocol(self):
        """Test that MemorySession implements SessionStorage."""
        session = MemorySession()
        assert isinstance(session, SessionStorage)
    
    def test_save_and_load(self):
        """Test saving and loading session data."""
        session = MemorySession()
        
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        
        session.save(data)
        loaded = session.load()
        
        assert loaded is not None
        assert loaded.email == "test@example.com"
        assert loaded.session_id == "sid123"
    
    def test_exists(self):
        """Test exists check."""
        session = MemorySession()
        
        assert session.exists() is False
        
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        session.save(data)
        
        assert session.exists() is True
    
    def test_delete(self):
        """Test deleting session."""
        session = MemorySession()
        
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        session.save(data)
        assert session.exists() is True
        
        session.delete()
        assert session.exists() is False
        assert session.load() is None
    
    def test_context_manager(self):
        """Test context manager usage."""
        with MemorySession() as session:
            data = SessionData(
                email="test@example.com",
                session_id="sid123",
                user_id="uid456",
                user_name="Test",
                master_key=b'\x00' * 16
            )
            session.save(data)
            assert session.exists() is True


class TestSQLiteSession:
    """Tests for SQLiteSession storage."""
    
    @pytest.fixture
    def temp_session(self):
        """Create a temporary session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = SQLiteSession("test_session", Path(tmpdir))
            yield session
            session.close()
    
    def test_implements_protocol(self, temp_session):
        """Test that SQLiteSession implements SessionStorage."""
        assert isinstance(temp_session, SessionStorage)
    
    def test_creates_session_file(self):
        """Test that session file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = SQLiteSession("my_account", Path(tmpdir))
            
            expected_path = Path(tmpdir) / "my_account.session"
            assert expected_path.exists()
            
            session.close()
    
    def test_save_and_load(self, temp_session):
        """Test saving and loading session data."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test User",
            master_key=b'\x01\x02\x03' + b'\x00' * 13,
            private_key=b'\xaa\xbb\xcc' + b'\x00' * 13
        )
        
        temp_session.save(data)
        loaded = temp_session.load()
        
        assert loaded is not None
        assert loaded.email == "test@example.com"
        assert loaded.session_id == "sid123"
        assert loaded.user_id == "uid456"
        assert loaded.user_name == "Test User"
        assert loaded.master_key == b'\x01\x02\x03' + b'\x00' * 13
        assert loaded.private_key == b'\xaa\xbb\xcc' + b'\x00' * 13
    
    def test_exists(self, temp_session):
        """Test exists check."""
        assert temp_session.exists() is False
        
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        temp_session.save(data)
        
        assert temp_session.exists() is True
    
    def test_delete(self, temp_session):
        """Test deleting session data."""
        data = SessionData(
            email="test@example.com",
            session_id="sid123",
            user_id="uid456",
            user_name="Test",
            master_key=b'\x00' * 16
        )
        temp_session.save(data)
        assert temp_session.exists() is True
        
        temp_session.delete()
        assert temp_session.exists() is False
        assert temp_session.load() is None
    
    def test_delete_file(self):
        """Test deleting session file completely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = SQLiteSession("test_session", Path(tmpdir))
            session_path = session.path
            
            # Save some data
            data = SessionData(
                email="test@example.com",
                session_id="sid123",
                user_id="uid456",
                user_name="Test",
                master_key=b'\x00' * 16
            )
            session.save(data)
            
            assert session_path.exists()
            
            # Delete file
            session.delete_file()
            
            assert not session_path.exists()
    
    def test_persistence(self):
        """Test that data persists across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First session - save data
            session1 = SQLiteSession("persistent", Path(tmpdir))
            data = SessionData(
                email="persistent@example.com",
                session_id="persistent_sid",
                user_id="persistent_uid",
                user_name="Persistent User",
                master_key=b'\x42' * 16
            )
            session1.save(data)
            session1.close()
            
            # Second session - load data
            session2 = SQLiteSession("persistent", Path(tmpdir))
            loaded = session2.load()
            session2.close()
            
            assert loaded is not None
            assert loaded.email == "persistent@example.com"
            assert loaded.session_id == "persistent_sid"
            assert loaded.master_key == b'\x42' * 16
    
    def test_overwrite_session(self, temp_session):
        """Test that saving overwrites existing session."""
        # First save
        data1 = SessionData(
            email="first@example.com",
            session_id="first_sid",
            user_id="first_uid",
            user_name="First",
            master_key=b'\x01' * 16
        )
        temp_session.save(data1)
        
        # Second save - should overwrite
        data2 = SessionData(
            email="second@example.com",
            session_id="second_sid",
            user_id="second_uid",
            user_name="Second",
            master_key=b'\x02' * 16
        )
        temp_session.save(data2)
        
        # Load should return second
        loaded = temp_session.load()
        
        assert loaded.email == "second@example.com"
        assert loaded.session_id == "second_sid"
    
    def test_context_manager(self):
        """Test context manager usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with SQLiteSession("context_test", Path(tmpdir)) as session:
                data = SessionData(
                    email="test@example.com",
                    session_id="sid123",
                    user_id="uid456",
                    user_name="Test",
                    master_key=b'\x00' * 16
                )
                session.save(data)
                assert session.exists() is True
    
    def test_path_property(self):
        """Test path property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = SQLiteSession("my_session", Path(tmpdir))
            
            assert session.path == Path(tmpdir) / "my_session.session"
            
            session.close()
    
    def test_custom_extension_path(self):
        """Test using full path with extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            full_path = Path(tmpdir) / "custom_name.session"
            session = SQLiteSession(str(full_path))
            
            assert session.path == full_path
            
            session.close()


class TestSessionIntegration:
    """Integration tests for session system."""
    
    def test_session_roundtrip(self):
        """Test complete session save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save session
            session = SQLiteSession("roundtrip", Path(tmpdir))
            
            original = SessionData(
                email="roundtrip@example.com",
                session_id="roundtrip_sid_12345",
                user_id="roundtrip_uid_67890",
                user_name="Roundtrip User",
                master_key=os.urandom(16),
                private_key=os.urandom(32),
                rsa_private_key_data=os.urandom(64)
            )
            
            session.save(original)
            session.close()
            
            # Load in new session
            session2 = SQLiteSession("roundtrip", Path(tmpdir))
            loaded = session2.load()
            session2.close()
            
            # Verify all fields
            assert loaded.email == original.email
            assert loaded.session_id == original.session_id
            assert loaded.user_id == original.user_id
            assert loaded.user_name == original.user_name
            assert loaded.master_key == original.master_key
            assert loaded.private_key == original.private_key
            assert loaded.rsa_private_key_data == original.rsa_private_key_data
    
    def test_memory_to_sqlite_migration(self):
        """Test migrating from memory to SQLite session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Start with memory session
            memory = MemorySession()
            
            data = SessionData(
                email="migrate@example.com",
                session_id="migrate_sid",
                user_id="migrate_uid",
                user_name="Migrate User",
                master_key=b'\x00' * 16
            )
            memory.save(data)
            
            # Migrate to SQLite
            sqlite = SQLiteSession("migrated", Path(tmpdir))
            memory_data = memory.load()
            if memory_data:
                sqlite.save(memory_data)
            
            # Verify migration
            loaded = sqlite.load()
            assert loaded.email == "migrate@example.com"
            assert loaded.session_id == "migrate_sid"
            
            sqlite.close()
