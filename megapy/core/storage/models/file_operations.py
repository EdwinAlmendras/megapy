"""File operations mixin."""
from typing import Optional
from pathlib import Path
from ...api import APIClient
from ...crypto import Base64Encoder, DecryptionService


class FileOperationsMixin:
    """Mixin for file download operations."""
    
    def __init__(self, api_client: APIClient = None):
        """Initializes file operations."""
        self.api = api_client
        self.encoder = Base64Encoder()
        self.decryption_service = DecryptionService()
    
    def download(self, path: Optional[str] = None, start: Optional[int] = None, end: Optional[int] = None) -> str:
        """Downloads file to local path."""
        if path is None:
            path = Path(self.name)
        else:
            path = Path(path)
            if path.is_dir():
                path = path / self.name
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        stream = self.get_stream(start, end)
        with path.open('wb') as f:
            for chunk in stream:
                f.write(chunk)
        
        return str(path)
    
    def get_stream(self, start: Optional[int] = None, end: Optional[int] = None):
        """Gets decrypted file stream."""
        url = self._get_download_url()
        
        full_size = self.size
        if start is None:
            start = 0
        if end is None:
            end = full_size - 1
        
        chunk_size = 1024 * 1024
        chunks = []
        
        for i in range(start, end + 1, chunk_size):
            chunk_end = min(i + chunk_size - 1, end)
            chunks.append((i, chunk_end))
        
        for chunk_start, chunk_end in chunks:
            chunk = self._download_chunk(url, chunk_start, chunk_end)
            decrypted_chunk = self._decrypt_chunk(chunk, chunk_start)
            yield decrypted_chunk
    
    def _get_download_url(self) -> str:
        """Gets download URL from API."""
        result = self.api.request({'a': 'g', 'g': 1, 'n': self.handle})
        return result['g']
    
    def _download_chunk(self, url: str, start: int, end: int) -> bytes:
        """Downloads chunk from URL."""
        headers = {'Range': f'bytes={start}-{end}'}
        response = self.api.session.get(url, headers=headers)
        return response.content
    
    def _decrypt_chunk(self, chunk: bytes, position: int) -> bytes:
        """Decrypts chunk."""
        if not hasattr(self, 'key') or not self.key:
            raise ValueError("Node key not available")
        key_bytes = self.encoder.decode(self.key) if isinstance(self.key, str) else self.key
        return self.decryption_service.decrypt_data(chunk, key_bytes, position)

