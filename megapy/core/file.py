import json
import base64
import binascii
import re
from urllib.parse import urlparse
from mega_py.crypto import mega_decrypt
from mega_py.types.file import FileProtocol
from mega_py.types.storage import StorageProtocol
from mega_py.types.file_node import FileNodeData
from pathlib import Path


class File(FileNodeData, FileProtocol):
    """
    MEGA file representation
    
    Handles file metadata and download operations
    """
    
    def __init__(self, storage: StorageProtocol, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """
        Initialize a file
        
        Args:
            storage: Storage instance
            handle: File handle
            data: File metadata
        """
        self.storage: StorageProtocol = storage
        
    @property
    def link(self):
        """Get public link to the file"""
        return f"https://mega.nz/file/{self.handle}#{base64.b64encode(self.key).decode().rstrip('=')}"
        
    def download(self, path=None, start=None, end=None):
        """
        Download file to path
        
        Args:
            path: Path-like object or string for local file path (defaults to current directory with file name)
            start: Start byte offset 
            end: End byte offset
            
        Returns:
            Path to downloaded file
        """
        # Convert path to Path object if string provided
        if path is None:
            path = Path(self.name)
        else:
            path = Path(path)
            if path.is_dir():
                path = path / self.name
                
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file stream
        stream = self.get_stream(start, end)
        
        # Write stream to file
        with path.open('wb') as f:
            for chunk in stream:
                f.write(chunk)
                
        return str(path)
        
    def get_stream(self, start=None, end=None):
        """
        Get a stream of decrypted file data
        
        Args:
            start: Start byte offset
            end: End byte offset
            
        Returns:
            Generator yielding decrypted chunks
        """
        # Get download URL
        url = self._get_download_url()
        
        # Calculate download range
        full_size = self.size
        if start is None:
            start = 0
        if end is None:
            end = full_size - 1
            
        # Calculate chunks
        chunk_size = 1024 * 1024  # 1MB chunks
        chunks = []
        
        for i in range(start, end + 1, chunk_size):
            chunk_end = min(i + chunk_size - 1, end)
            chunks.append((i, chunk_end))
            
        # Yield decrypted chunks
        for chunk_start, chunk_end in chunks:
            chunk = self._download_chunk(url, chunk_start, chunk_end)
            decrypted_chunk = self._decrypt_chunk(chunk, chunk_start)
            yield decrypted_chunk
        
    def _get_download_url(self):
        """
        Get download URL for the file
        
        Returns:
            Download URL
        """
        result = self.storage.api.get_download_url(self.handle)
        
        return result['g']
        
    def _download_chunk(self, url, start, end):
        """
        Download a chunk of the file
        
        Args:
            url: Download URL
            start: Start byte
            end: End byte
            
        Returns:
            Encrypted chunk data
        """
        headers = {
            'Range': f'bytes={start}-{end}'
        }
        
        response = self.storage.api.session.get(url, headers=headers)
        return response.content
        
    def _decrypt_chunk(self, chunk, position):
        """
        Decrypt a chunk
        
        Args:
            chunk: Encrypted chunk data
            position: Chunk position in the file
            
        Returns:
            Decrypted data
        """
        # Determine which part of the key to use based on position
        key = self.key
        
        # Decrypt the chunk
        return mega_decrypt(chunk, key)
        
    @staticmethod
    def from_url(url, api=None):
        """
        Create a File instance from a MEGA url
        
        Args:
            url: MEGA file URL
            api: Optional API instance
            
        Returns:
            File instance
        """
        # Import storage here to avoid circular imports
        from mega_py.api import API
        from mega_py.storage import Storage
        
        if api is None:
            api = API(keepalive=False)
            
        # Parse URL
        parsed = urlparse(url)
        path = parsed.path
        
        # Extract file handle
        match = re.search(r'\/file\/([^#]+)', path)
        if not match:
            raise ValueError(f"Invalid MEGA URL: {url}")
            
        handle = match.group(1)
        
        # Extract key from URL fragment
        key = parsed.fragment
        if not key:
            raise ValueError(f"Missing key in MEGA URL: {url}")
            
        # Pad key if needed for base64 decoding
        padding = len(key) % 4
        if padding:
            key += '=' * (4 - padding)
            
        # Decode key
        try:
            key_bytes = base64.b64decode(key)
        except binascii.Error:
            raise ValueError(f"Invalid key in MEGA URL: {url}")
            
        # Get file metadata
        result = api.request({
            'a': 'g',
            'p': handle,
            'ssl': 1
        })
        
        # Create a dummy storage instance
        storage = Storage(None, None, None, {'api': api})
        
        # Create file data
        file_data = {
            'h': handle,
            'p': None,
            't': 0,
            's': result.get('s', 0),
            'k': key_bytes
        }
        
        # Try to decrypt attributes if available
        if 'at' in result:
            try:
                attrs = mega_decrypt(base64.b64decode(result['at']), key_bytes).decode()
                attrs_dict = json.loads(attrs)
                file_data['attrs'] = attrs_dict
            except Exception:
                file_data['attrs'] = {'n': handle}
                
        # Create file instance
        return File(storage, handle, file_data)
        
    def move(self, target):
        """
        Move file to another folder
        
        Args:
            target: Target folder handle
            
        Returns:
            True if successful
        """
        result = self.storage.api.move(self.handle, target)
        
        # Update local data
        
        if result['e'] == 0:
            self.storage.files[self.handle]['p'] = target
            self.path = target
            
        return result['e'] == 0
        
    def rename(self, new_name):
        """
        Rename file
        
        Args:
            new_name: New file name
            
        Returns:
            True if successful
        """
        # Update attributes
        attrs = dict(self.attrs)
        attrs['n'] = new_name
        
        # Encrypt attributes
        from .attributes import encrypt_attr
        encrypted_attrs = encrypt_attr(attrs, self.key, self.type)
        
        result = self.storage.api.rename(self.handle, encrypted_attrs)
        
        # Update local data
        if result['e'] == 0:
            self.attrs['n'] = new_name
            self.data['attrs'] = attrs
            
        return result['e'] == 0
        
    def delete(self, permanent=False):
        """
        Delete file
        
        Args:
            permanent: If True, delete permanently, otherwise move to trash
            
        Returns:
            True if successful
        """
        return self.storage.delete(self.handle, permanent)


