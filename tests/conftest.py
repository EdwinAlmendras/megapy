"""Pytest fixtures for MegaPy tests."""
import pytest
from Crypto.Random import get_random_bytes


@pytest.fixture
def master_key():
    """Generates a 16-byte master key for testing."""
    return get_random_bytes(16)


@pytest.fixture
def node_key():
    """Generates a 32-byte node key for testing."""
    return get_random_bytes(32)


@pytest.fixture
def file_key():
    """Generates a 24-byte file key (16 AES + 8 nonce)."""
    return get_random_bytes(24)


@pytest.fixture
def sample_node_data():
    """Returns sample node data from MEGA API."""
    return {
        'h': 'test_handle_123',
        'p': 'parent_handle',
        't': 0,
        's': 1024,
        'ts': 1699900000,
        'u': 'user_handle',
        'k': 'user_handle:encrypted_key_base64',
        'a': 'encrypted_attributes'
    }


@pytest.fixture
def sample_folder_node_data():
    """Returns sample folder node data."""
    return {
        'h': 'folder_handle_456',
        'p': 'parent_handle',
        't': 1,
        'ts': 1699900000,
        'u': 'user_handle',
        'k': 'user_handle:encrypted_key_base64',
        'a': 'encrypted_attributes'
    }
