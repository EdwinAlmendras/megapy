"""Tests for storage models."""
import pytest
from unittest.mock import Mock, MagicMock, patch

from megapy.core.storage.models.node import Node
from megapy.core.storage.models.file_node import FileNode
from megapy.core.storage.models.folder_node import FolderNode


class ConcreteNode(Node):
    """Concrete implementation of Node for testing."""
    pass


class TestNode:
    """Test suite for Node base class."""
    
    @pytest.fixture
    def node(self):
        """Create a basic node."""
        return ConcreteNode(
            handle='test_handle',
            parent_handle='parent',
            node_type=0,
            size=1024,
            creation_date=1699900000,
            owner='owner_id',
            key='base64_key',
            attributes={'n': 'test_file.txt'}
        )
    
    def test_init_basic(self, node):
        """Test basic initialization."""
        assert node.handle == 'test_handle'
        assert node.parent_handle == 'parent'
        assert node.type == 0
        assert node.size == 1024
        assert node.name == 'test_file.txt'
    
    def test_init_defaults(self):
        """Test default values."""
        node = ConcreteNode(handle='handle')
        
        assert node.parent_handle is None
        assert node.type == 0
        assert node.size == 0
        assert node.key is None
        assert node.name == 'handle'
    
    def test_is_dir_file(self, node):
        """Test is_dir for file."""
        assert node.is_dir is False
    
    def test_is_dir_folder(self):
        """Test is_dir for folder."""
        node = ConcreteNode(handle='folder', node_type=1)
        assert node.is_dir is True
    
    def test_add_child(self, node):
        """Test adding child node."""
        child = ConcreteNode(handle='child')
        
        node.add_child(child)
        
        assert child in node.get_children()
        assert child.get_parent() is node
    
    def test_add_child_duplicate(self, node):
        """Test adding same child twice."""
        child = ConcreteNode(handle='child')
        
        node.add_child(child)
        node.add_child(child)
        
        assert len(node.get_children()) == 1
    
    def test_remove_child(self, node):
        """Test removing child node."""
        child = ConcreteNode(handle='child')
        node.add_child(child)
        
        node.remove_child(child)
        
        assert child not in node.get_children()
        assert child.get_parent() is None
    
    def test_get_children_returns_copy(self, node):
        """Test get_children returns a copy."""
        child = ConcreteNode(handle='child')
        node.add_child(child)
        
        children = node.get_children()
        children.clear()
        
        assert len(node.get_children()) == 1
    
    def test_get_path_root(self):
        """Test path for root node."""
        node = ConcreteNode(handle='root', attributes={'n': 'Root'})
        
        assert node.get_path() == '/Root'
    
    def test_get_path_nested(self):
        """Test path for nested node."""
        root = ConcreteNode(handle='root', attributes={'n': 'Root'})
        folder = ConcreteNode(handle='folder', attributes={'n': 'Documents'})
        file = ConcreteNode(handle='file', attributes={'n': 'test.txt'})
        
        root.add_child(folder)
        folder.add_child(file)
        
        assert file.get_path() == '/Root/Documents/test.txt'
    
    def test_find_child(self, node):
        """Test finding child by name."""
        child1 = ConcreteNode(handle='c1', attributes={'n': 'file1.txt'})
        child2 = ConcreteNode(handle='c2', attributes={'n': 'file2.txt'})
        
        node.add_child(child1)
        node.add_child(child2)
        
        found = node.find_child('file1.txt')
        
        assert found is child1
    
    def test_find_child_not_found(self, node):
        """Test finding non-existent child."""
        found = node.find_child('nonexistent')
        
        assert found is None
    
    def test_find_by_path(self):
        """Test finding node by path."""
        root = ConcreteNode(handle='root', attributes={'n': 'Root'})
        folder = ConcreteNode(handle='folder', attributes={'n': 'Documents'})
        file = ConcreteNode(handle='file', attributes={'n': 'test.txt'})
        
        root.add_child(folder)
        folder.add_child(file)
        
        found = root.find_by_path('Documents/test.txt')
        
        assert found is file
    
    def test_find_by_path_not_found(self):
        """Test finding non-existent path."""
        root = ConcreteNode(handle='root', attributes={'n': 'Root'})
        
        found = root.find_by_path('nonexistent/path')
        
        assert found is None
    
    def test_find_by_path_empty(self, node):
        """Test finding with empty path."""
        found = node.find_by_path('')
        
        assert found is node
    
    def test_rename(self, node):
        """Test renaming node."""
        node.rename('new_name.txt')
        
        assert node.name == 'new_name.txt'
        assert node.attributes['n'] == 'new_name.txt'
    
    def test_move(self):
        """Test moving node to new parent."""
        old_parent = ConcreteNode(handle='old', attributes={'n': 'Old'})
        new_parent = ConcreteNode(handle='new', attributes={'n': 'New'})
        child = ConcreteNode(handle='child', attributes={'n': 'File'})
        
        old_parent.add_child(child)
        child.move(new_parent)
        
        assert child not in old_parent.get_children()
        assert child in new_parent.get_children()
        assert child.parent_handle == 'new'
    
    def test_update_attributes(self, node):
        """Test updating attributes."""
        node.update_attributes({'n': 'updated.txt', 'lbl': 1})
        
        assert node.name == 'updated.txt'
        assert node.attributes['lbl'] == 1
    
    def test_to_dict(self, node):
        """Test converting to dictionary."""
        result = node.to_dict()
        
        assert result['handle'] == 'test_handle'
        assert result['parent'] == 'parent'
        assert result['type'] == 0
        assert result['size'] == 1024
        assert result['name'] == 'test_file.txt'


class TestFileNode:
    """Test suite for FileNode."""
    
    @pytest.fixture
    def file_node(self):
        """Create a file node."""
        return FileNode(
            handle='file_handle',
            node_type=0,
            size=2048,
            key='dGVzdF9rZXlfMTIzNDU2Nzg5MDEyMzQ1Ng',
            attributes={'n': 'document.pdf'}
        )
    
    def test_init_basic(self, file_node):
        """Test basic initialization."""
        assert file_node.handle == 'file_handle'
        assert file_node.is_dir is False
        assert file_node.size == 2048
    
    def test_init_with_type_kwarg(self):
        """Test initialization with 'type' instead of 'node_type'."""
        node = FileNode(handle='handle', type=0, size=100)
        
        assert node.type == 0
    
    def test_link_property(self, file_node):
        """Test link property generates URL."""
        link = file_node.link
        
        assert 'mega.nz/file/' in link
        assert file_node.handle in link
    
    def test_link_without_key(self):
        """Test link with no key returns empty."""
        node = FileNode(handle='handle')
        
        assert node.link == ''
    
    def test_is_file_operations_mixin(self, file_node):
        """Test has FileOperationsMixin attributes."""
        assert hasattr(file_node, 'download')
        assert hasattr(file_node, 'get_stream')


class TestFolderNode:
    """Test suite for FolderNode."""
    
    @pytest.fixture
    def folder_node(self):
        """Create a folder node."""
        return FolderNode(
            handle='folder_handle',
            node_type=1,
            attributes={'n': 'Documents'}
        )
    
    def test_init_basic(self, folder_node):
        """Test basic initialization."""
        assert folder_node.handle == 'folder_handle'
        assert folder_node.is_dir is True
        assert folder_node.name == 'Documents'
    
    def test_init_defaults_to_type_1(self):
        """Test folder node defaults to type 1."""
        node = FolderNode(handle='handle')
        
        assert node.type == 1
        assert node.is_dir is True
    
    def test_list_files(self, folder_node):
        """Test listing files."""
        file1 = FileNode(handle='f1', attributes={'n': 'file1.txt'})
        file2 = FileNode(handle='f2', attributes={'n': 'file2.txt'})
        subfolder = FolderNode(handle='sf', attributes={'n': 'Subfolder'})
        
        folder_node.add_child(file1)
        folder_node.add_child(file2)
        folder_node.add_child(subfolder)
        
        files = folder_node.list_files()
        
        assert len(files) == 2
        assert file1 in files
        assert file2 in files
        assert subfolder not in files
    
    def test_list_folders(self, folder_node):
        """Test listing folders."""
        file1 = FileNode(handle='f1', attributes={'n': 'file1.txt'})
        subfolder1 = FolderNode(handle='sf1', attributes={'n': 'Folder1'})
        subfolder2 = FolderNode(handle='sf2', attributes={'n': 'Folder2'})
        
        folder_node.add_child(file1)
        folder_node.add_child(subfolder1)
        folder_node.add_child(subfolder2)
        
        folders = folder_node.list_folders()
        
        assert len(folders) == 2
        assert subfolder1 in folders
        assert subfolder2 in folders
        assert file1 not in folders
    
    def test_list_files_empty(self, folder_node):
        """Test listing files from empty folder."""
        files = folder_node.list_files()
        
        assert files == []
    
    def test_list_folders_empty(self, folder_node):
        """Test listing folders from empty folder."""
        folders = folder_node.list_folders()
        
        assert folders == []


class TestNodeHierarchy:
    """Test node hierarchy operations."""
    
    def test_deep_nesting(self):
        """Test deeply nested structure."""
        root = FolderNode(handle='root', attributes={'n': 'Root'})
        current = root
        
        for i in range(10):
            child = FolderNode(handle=f'folder_{i}', attributes={'n': f'Level{i}'})
            current.add_child(child)
            current = child
        
        # Add file at bottom
        file = FileNode(handle='file', attributes={'n': 'deep.txt'})
        current.add_child(file)
        
        # Find it
        path = '/'.join([f'Level{i}' for i in range(10)]) + '/deep.txt'
        found = root.find_by_path(path)
        
        assert found is file
    
    def test_multiple_children(self):
        """Test folder with many children."""
        folder = FolderNode(handle='folder', attributes={'n': 'Folder'})
        
        for i in range(100):
            child = FileNode(handle=f'file_{i}', attributes={'n': f'file_{i}.txt'})
            folder.add_child(child)
        
        assert len(folder.get_children()) == 100
        assert len(folder.list_files()) == 100
    
    def test_mixed_children(self):
        """Test folder with mixed file/folder children."""
        root = FolderNode(handle='root', attributes={'n': 'Root'})
        
        # Add mixed children
        for i in range(5):
            folder = FolderNode(handle=f'folder_{i}', attributes={'n': f'Folder{i}'})
            root.add_child(folder)
            
            for j in range(3):
                file = FileNode(handle=f'file_{i}_{j}', attributes={'n': f'file{j}.txt'})
                folder.add_child(file)
        
        assert len(root.list_folders()) == 5
        assert len(root.list_files()) == 0
        
        for folder in root.list_folders():
            assert len(folder.list_files()) == 3
