"""
Upload coordinator for MEGA uploads.

This module coordinates the entire MEGA upload process.
"""
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Final
from mega_py.upload.types.upload_types import (
    ChunkData, EncryptedChunk, ChunkMAC, MetaMAC, FileAttributes,
    UploadToken, ChunkBoundary, LoggerProtocol, ApiProtocol
)
from mega_py.upload.file_validator import FileValidator
from mega_py.upload.chunking_strategy import MegaChunkingStrategy
from mega_py.upload.crypto_handler import MegaEncrypt   
from mega_py.upload.chunk_uploader import ChunkUploader
from mega_py.upload.file_reader import FileReader
from mega_py.upload.node_creator import NodeCreator
from utils.logger import setup_logger
import logging
class UploadCoordinator:
    """
    Coordinates the entire MEGA upload process.
    
    This class orchestrates the entire upload process by:
    - Validating the file
    - Obtaining an upload URL
    - Dividing the file into chunks
    - Managing parallel uploads
    - Processing chunk encryption
    - Creating the final node in MEGA
    
    Attributes:
        file_path: Path to the file to upload
        target_id: Target folder node ID in MEGA
        api: MEGA API client 
        logger: Logger instance
    """
    
    # Default settings
    DEFAULT_MAX_CONCURRENT_UPLOADS: Final[int] = 4
    
    def __init__(
        self,
        file_path: Path,
        target_id: str,
        api: ApiProtocol,
        master_key: bytes,
        attributes: Optional[FileAttributes] = None,
        max_concurrent_uploads: int = DEFAULT_MAX_CONCURRENT_UPLOADS,
        logger: LoggerProtocol = None,
        encryption_key: Optional[bytes] = None,
        level = logging.INFO
    ) -> None:
        """
        Initialize the upload coordinator.
        
        Args:
            file_path: Path to the file to upload
            target_id: Target folder node ID in MEGA
            api: MEGA API client
            master_key: Master encryption key for node creation
            attributes: File attributes (optional)
            max_concurrent_uploads: Maximum number of concurrent uploads
            logger: Logger instance (optional)
            encryption_key: Custom encryption key (optional)
            
        Raises:
            ValueError: If any parameters are invalid
        """
        # Set up logger
        self.logger = logger or setup_logger("UploadCoordinator", level)
        
        # Validate parameters
        if not file_path:
            raise ValueError("File path is required")
        if not target_id:
            raise ValueError("Target ID is required")
        if not api:
            raise ValueError("API client is required")
        if not master_key:
            raise ValueError("Master key is required")
            
        # Store parameters
        self.file_path = file_path
        self.target_id = target_id
        self.api = api
        self.master_key = master_key
        self.max_concurrent_uploads = max_concurrent_uploads
        
        # Process attributes
        if not attributes:
            self.attributes = {"name": file_path.name}
        else:
            self.attributes = attributes
            
        # Initialize crypto handler
        if encryption_key:
            self.crypto_handler = MegaEncrypt(encryption_key)
        else:
            encryption_key = os.urandom(24)
            self.crypto_handler = MegaEncrypt(encryption_key)
            
        # Initialize sub-components
        self.file_validator = FileValidator(self.logger)
        self.chunking_strategy = MegaChunkingStrategy(logger=self.logger)
        self.file_reader = FileReader(self.logger)
        self.chunk_uploader = None  # Will be initialized after getting upload URL
        self.node_creator = NodeCreator(api, master_key, self.logger)
        
        # State tracking
        self.upload_url: Optional[str] = None
        self.upload_token: Optional[UploadToken] = None
        self.chunk_macs: List[ChunkMAC] = []
        self.meta_mac: Optional[MetaMAC] = None
        self.final_key: Optional[bytes] = None
        
    async def upload(self) -> Dict[str, Any]:
        """
        Execute the complete upload process.
        
        Returns:
            Data from the created node
            
        Raises:
            ValueError: If the upload fails
        """
        self.logger.info(f"Starting upload of {self.file_path}")
        
        # Validate and get file size
        path, file_size = self.file_validator.validate_and_prepare(self.file_path)
        
        # Get upload URL
        await self._get_upload_url(file_size)
        
        # Initialize chunk uploader with the URL
        self.chunk_uploader = ChunkUploader(self.upload_url, self.logger)
        
        # Upload file chunks
        await self._upload_file_chunks(file_size)
        
        # Compute meta MAC and get final key
        self.final_key = self.crypto_handler.finalize()
        
        # Create node
        result = await self.node_creator.create_node(
            self.upload_token,
            self.target_id,
            self.final_key,
            self.attributes
        )
        
        self.logger.info(f"Upload of {self.file_path} completed successfully")
        return result
    
    async def _get_upload_url(self, size: int) -> None:
        """
        Get upload URL from MEGA API.
        
        Args:
            size: File size in bytes
            
        Raises:
            ValueError: If unable to get upload URL
        """
        self.logger.debug(f"Requesting upload URL for file size: {size} bytes")
        
        try:
            result = self.api.request({
                'a': 'u',  # upload
                's': size  # size
            })
            
            if 'p' not in result:
                raise ValueError("Could not obtain upload URL: invalid server response")
                
            self.upload_url = result['p']
            self.logger.debug(f"Upload URL obtained: {self.upload_url}")
            
        except Exception as e:
            error_msg = f"Error getting upload URL: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
    async def _upload_file_chunks(self, file_size: int) -> None:
        """
        Upload file chunks secuencialmente (cifrado y subida en orden).
        
        IMPORTANTE: El cifrado AES-CTR debe ser secuencial, y cada chunk se sube
        completamente antes de procesar el siguiente.
        
        Args:
            file_size: File size in bytes
            
        Raises:
            ValueError: If chunk upload fails
        """
        # Calculate chunk boundaries
        chunks = self.chunking_strategy.calculate_chunks(file_size)
        
        # Initialize chunk MACs list
        self.chunk_macs = [None] * len(chunks)
        
        total_chunks = len(chunks)
        self.logger.info(f"Procesando {total_chunks} chunks secuencialmente (cifrado + subida)")
        
        # Procesar todos los chunks en orden secuencial
        for i in range(total_chunks):
            start, end = chunks[i]
            
            # 1. Leer y cifrar chunk (secuencial)
            chunk_data = await self.file_reader.read_chunk(self.file_path, start, end)
            if not chunk_data:
                raise ValueError(f"No se pudo leer el chunk {i}")
            
            # El cifrado debe ser secuencial para mantener el contador CTR correcto
            encrypted_chunk = self.crypto_handler.encrypt(i, chunk_data)
            
            # 2. Subir chunk y esperar a que termine antes de continuar
            try:
                await self._upload_and_track(i, start, encrypted_chunk)
            except Exception as e:
                self.logger.error(f"Error al subir chunk {i}: {str(e)}")
                raise ValueError(f"Error en la subida del chunk {i}: {str(e)}")
            
            # 3. Actualizar progreso
            progress_percent = int((i + 1) / total_chunks * 100)
            if (i + 1) % 10 == 0 or (i + 1) == total_chunks:
                self.logger.info(f"Progreso: {i + 1}/{total_chunks} chunks ({progress_percent}%)")
        
        self.logger.info(f"Subida completa: {total_chunks} chunks procesados")
        self.upload_token = self.chunk_uploader.get_upload_token()
    async def _upload_and_track(self, index: int, start: int, encrypted_chunk: bytes) -> None:
        """
        Subir un chunk y actualizar su estado.
        
        Args:
            index: Índice del chunk
            start: Posición de inicio 
            encrypted_chunk: Datos cifrados
        """
        await self.chunk_uploader.upload_chunk(index, start, encrypted_chunk)
        #self.logger.debug(f"Chunk {index} subido correctamente") 