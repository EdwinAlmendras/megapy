"""
Chunking strategies for MEGA uploads.

This module defines strategies for splitting files into chunks for MEGA uploads.
"""
from typing import List, Tuple, Protocol, Final
from mega_py.upload.types.upload_types import FileSize, ChunkSize, Position, ChunkBoundary, LoggerProtocol

class ChunkingStrategy(Protocol):
    """Protocol for chunking strategies."""
    def calculate_chunks(self, file_size: FileSize) -> List[ChunkBoundary]: ...

class MegaChunkingStrategy:
    """
    Implements MEGA's specific chunking strategy for file uploads.
    
    MEGA usa límites de chunks específicos según la documentación oficial:
    0 / 128K / 384K / 768K / 1280K / 1920K / 2688K / 3584K / 4608K / ... (cada 1024 KB adicional) / EOF
    
    Attributes:
        logger: Logger instance
    """
    
    def __init__(self, logger: LoggerProtocol = None) -> None:
        """
        Initialize the MEGA chunking strategy.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        
        # Secuencia específica de límites de chunks de MEGA en bytes
        # Primeros 8 límites: 0, 128K, 384K, 768K, 1280K, 1920K, 2688K, 3584K
        self.chunk_boundaries = [
            0,                     # 0
            128 * 1024,            # 128K
            384 * 1024,            # 384K
            768 * 1024,            # 768K
            1280 * 1024,           # 1280K
            1920 * 1024,           # 1920K
            2688 * 1024,           # 2688K
            3584 * 1024            # 3584K
        ]
        
        # A partir de 4608K, cada límite aumenta en 1024K
        current = 4608 * 1024      # 4608K
        # Agregar límites adicionales hasta un tamaño razonable
        # Esto cubre hasta ~1GB, para archivos más grandes se calcularán dinámicamente
        while current < 1024 * 1024 * 1024:  # 1GB
            self.chunk_boundaries.append(current)
            current += 1024 * 1024  # Incremento de 1024K
    
    def calculate_chunks(self, file_size: FileSize) -> List[ChunkBoundary]:
        """
        Calculate chunk boundaries for a file of the given size.
        
        Args:
            file_size: Total file size in bytes
            
        Returns:
            List of (start, end) tuples representing chunk boundaries
        """
        if self.logger:
            self.logger.debug(f"Calculating MEGA-specific chunks for file size: {file_size} bytes")
        
        # Asegurar que tenemos suficientes límites de chunks para el tamaño del archivo
        self._ensure_boundaries_for_size(file_size)
            
        chunks: List[ChunkBoundary] = []
        
        # Encontrar todos los límites de chunks que aplican para este tamaño de archivo
        applicable_boundaries = [b for b in self.chunk_boundaries if b < file_size]
        applicable_boundaries.append(file_size)  # Añadir EOF
        
        # Crear chunks basados en los límites aplicables
        for i in range(len(applicable_boundaries) - 1):
            start = applicable_boundaries[i]
            end = applicable_boundaries[i + 1]
            chunks.append((start, end))
        
        if self.logger:
            self.logger.debug(f"File will be uploaded in {len(chunks)} chunks")
            chunk_sizes = [end-start for start, end in chunks]
            self.logger.debug(f"Chunk sizes (bytes): {chunk_sizes}")
            
        return chunks
    
    def _ensure_boundaries_for_size(self, size: FileSize) -> None:
        """
        Asegura que tenemos suficientes límites de chunks para el tamaño del archivo.
        
        Args:
            size: Tamaño del archivo en bytes
        """
        if size > self.chunk_boundaries[-1]:
            current = self.chunk_boundaries[-1]
            while current < size:
                current += 1024 * 1024  # Incremento de 1024K
                self.chunk_boundaries.append(current)
                
            if self.logger:
                self.logger.debug(f"Extended chunk boundaries to cover file size: {size} bytes") 