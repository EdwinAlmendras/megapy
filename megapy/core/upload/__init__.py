"""
Upload module for MEGA file uploads.

This module provides a clean, SOLID-compliant interface for uploading files to MEGA.
Follows Open/Closed Principle with pluggable strategies for encryption and chunking.
"""
from .facade import UploadFacade
from .coordinator import UploadCoordinator
from .models import UploadResult, UploadConfig, FileAttributes, UploadProgress
from .protocols import (
    ChunkingStrategy,
    EncryptionStrategy,
    FileReaderProtocol,
    ChunkUploaderProtocol,
    NodeCreatorProtocol
)

__all__ = [
    # Main classes
    'UploadFacade',
    'UploadCoordinator',
    
    # Models
    'UploadResult',
    'UploadConfig',
    'FileAttributes',
    'UploadProgress',
    
    # Protocols
    'ChunkingStrategy',
    'EncryptionStrategy',
    'FileReaderProtocol',
    'ChunkUploaderProtocol',
    'NodeCreatorProtocol',
]
