"""Tests for node processor."""
import pytest
from unittest.mock import Mock, MagicMock
from Crypto.Random import get_random_bytes

from megapy.core.storage.processors.node_processor import NodeProcessor
from megapy.core.storage.processors.node_factory import NodeFactory


class TestNodeProcessor:
    """Test suite for NodeProcessor."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        repo = Mock()
        repo.get_all_nodes = Mock(return_value=[])
        repo.get_shared_keys = Mock(return_value={})
        return repo
    
    @pytest.fixture
    def mock_key_decryptor(self):
        """Create mock key decryptor."""
        decryptor = Mock()
        decryptor.decrypt = Mock(return_value=get_random_bytes(32))
        return decryptor
    
    @pytest.fixture
    def mock_attr_decryptor(self):
        """Create mock attribute decryptor."""
        decryptor = Mock()
        decryptor.decrypt = Mock(return_value={'n': 'test_file.txt'})
        return decryptor
    
    @pytest.fixture
    def processor(self, mock_repository, mock_key_decryptor, mock_attr_decryptor):
        """Create processor instance."""
        return NodeProcessor(
            mock_repository,
            mock_key_decryptor,
            mock_attr_decryptor
        )
    
    def test_process_empty_nodes(self, processor):
        """Test processing empty node list."""
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes([], master_key, {})
        
        assert result == {}
    
    def test_process_root_node(self, processor):
        """Test processing root (drive) node."""
        nodes = [{
            'h': 'root_handle',
            't': NodeProcessor.NODE_TYPE_DRIVE,
            'p': None
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'root_handle' in result
        assert result['root_handle']['name'] == 'Root'
        assert result['root_handle']['is_dir'] is True
    
    def test_process_trash_node(self, processor):
        """Test processing trash bin node."""
        nodes = [{
            'h': 'trash_handle',
            't': NodeProcessor.NODE_TYPE_RUBBISH_BIN,
            'p': None
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'trash_handle' in result
        assert result['trash_handle']['name'] == 'Trash'
    
    def test_process_inbox_node(self, processor):
        """Test processing inbox node."""
        nodes = [{
            'h': 'inbox_handle',
            't': NodeProcessor.NODE_TYPE_INBOX,
            'p': None
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'inbox_handle' in result
        assert result['inbox_handle']['name'] == 'Inbox'
    
    def test_process_file_node(
        self, mock_repository, mock_key_decryptor, mock_attr_decryptor
    ):
        """Test processing file node."""
        mock_attr_decryptor.decrypt.return_value = {'n': 'document.pdf'}
        processor = NodeProcessor(
            mock_repository, mock_key_decryptor, mock_attr_decryptor
        )
        
        nodes = [{
            'h': 'file_handle',
            't': 0,
            'p': 'parent',
            's': 1024,
            'ts': 1699900000,
            'u': 'owner',
            'k': 'owner:encrypted_key',
            'a': 'encrypted_attrs'
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'file_handle' in result
        assert result['file_handle']['is_dir'] is False
        assert result['file_handle']['name'] == 'document.pdf'
    
    def test_process_folder_node(
        self, mock_repository, mock_key_decryptor, mock_attr_decryptor
    ):
        """Test processing folder node."""
        mock_attr_decryptor.decrypt.return_value = {'n': 'Documents'}
        processor = NodeProcessor(
            mock_repository, mock_key_decryptor, mock_attr_decryptor
        )
        
        nodes = [{
            'h': 'folder_handle',
            't': 1,
            'p': 'parent',
            'ts': 1699900000,
            'u': 'owner',
            'k': 'owner:encrypted_key',
            'a': 'encrypted_attrs'
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'folder_handle' in result
        assert result['folder_handle']['is_dir'] is True
        assert result['folder_handle']['name'] == 'Documents'
    
    def test_process_skips_node_without_handle(self, processor):
        """Test processing skips nodes without handle."""
        nodes = [{'t': 0, 'p': 'parent'}]  # Missing 'h'
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert result == {}
    
    def test_process_skips_node_when_key_decrypt_fails(
        self, mock_repository, mock_attr_decryptor
    ):
        """Test skips node when key decryption fails."""
        failing_decryptor = Mock()
        failing_decryptor.decrypt = Mock(return_value=None)
        
        processor = NodeProcessor(
            mock_repository, failing_decryptor, mock_attr_decryptor
        )
        
        nodes = [{
            'h': 'handle',
            't': 0,
            'k': 'owner:key',
            'a': 'attrs'
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        assert 'handle' not in result
    
    def test_process_handles_attr_decrypt_exception(
        self, mock_repository, mock_key_decryptor
    ):
        """Test handles attribute decryption exception gracefully."""
        failing_attr = Mock()
        failing_attr.decrypt = Mock(side_effect=Exception("Decrypt error"))
        
        processor = NodeProcessor(
            mock_repository, mock_key_decryptor, failing_attr
        )
        
        nodes = [{
            'h': 'handle',
            't': 0,
            'k': 'owner:key',
            'a': 'attrs'
        }]
        master_key = get_random_bytes(16)
        
        result = processor.process_nodes(nodes, master_key, {})
        
        # Should still create node with fallback attributes
        assert 'handle' in result
    
    def test_process_all_calls_repository(
        self, mock_repository, mock_key_decryptor, mock_attr_decryptor
    ):
        """Test process_all uses repository."""
        mock_repository.get_all_nodes.return_value = []
        mock_repository.get_shared_keys.return_value = {}
        
        processor = NodeProcessor(
            mock_repository, mock_key_decryptor, mock_attr_decryptor
        )
        
        master_key = get_random_bytes(16)
        result = processor.process_all(master_key)
        
        mock_repository.get_all_nodes.assert_called_once()
        mock_repository.get_shared_keys.assert_called_once()
    
    def test_create_special_node(self, processor):
        """Test _create_special_node helper."""
        result = processor._create_special_node('handle', 'Test', 2)
        
        assert result['handle'] == 'handle'
        assert result['name'] == 'Test'
        assert result['type'] == 2
        assert result['is_dir'] is True
        assert result['parent'] is None


class TestNodeFactory:
    """Test suite for NodeFactory."""
    
    @pytest.fixture
    def factory(self):
        """Create factory instance."""
        return NodeFactory()
    
    def test_create_node_data_basic(self, factory):
        """Test basic node data creation."""
        node = {
            'h': 'handle123',
            'p': 'parent_handle',
            't': 0,
            's': 2048,
            'ts': 1699900000,
            'u': 'user123'
        }
        node_key = get_random_bytes(32)
        attributes = {'n': 'test.txt'}
        
        result = factory.create_node_data(node, node_key, attributes)
        
        assert result['handle'] == 'handle123'
        assert result['parent'] == 'parent_handle'
        assert result['is_dir'] is False
        assert result['size'] == 2048
        assert result['name'] == 'test.txt'
    
    def test_create_node_data_folder(self, factory):
        """Test folder node data creation."""
        node = {
            'h': 'folder123',
            'p': 'parent',
            't': 1,
            'ts': 1699900000
        }
        node_key = get_random_bytes(32)
        attributes = {'n': 'Documents'}
        
        result = factory.create_node_data(node, node_key, attributes)
        
        assert result['is_dir'] is True
        assert result['name'] == 'Documents'
    
    def test_create_node_data_without_attributes(self, factory):
        """Test node data creation without attributes."""
        node = {
            'h': 'handle',
            't': 0
        }
        node_key = get_random_bytes(32)
        
        result = factory.create_node_data(node, node_key, None)
        
        assert result['name'] == 'handle'
    
    def test_create_node_data_encodes_key(self, factory):
        """Test node key is Base64 encoded."""
        node = {'h': 'handle', 't': 0}
        node_key = get_random_bytes(32)
        
        result = factory.create_node_data(node, node_key, None)
        
        assert isinstance(result['key'], str)
        # Should be URL-safe base64
        assert '+' not in result['key']
        assert '/' not in result['key']
    
    def test_create_node_data_null_key(self, factory):
        """Test node data with null key."""
        node = {'h': 'handle', 't': 0}
        
        result = factory.create_node_data(node, None, None)
        
        assert result['key'] is None
    
    def test_create_node_data_defaults(self, factory):
        """Test default values."""
        node = {'h': 'handle'}
        
        result = factory.create_node_data(node, None, None)
        
        assert result['size'] == 0
        assert result['creation_date'] == 0
        assert result['owner'] is None
        assert result['parent'] is None
