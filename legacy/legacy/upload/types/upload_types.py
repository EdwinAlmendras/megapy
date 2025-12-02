"""
Type definitions for the MEGA upload module.
"""
from typing import Dict, Any, Union, List, Protocol, Tuple, Optional, Callable, TypeAlias
from pathlib import Path
import logging

# Basic type aliases
FileKey: TypeAlias = bytes
FileSize: TypeAlias = int
ChunkSize: TypeAlias = int
Position: TypeAlias = int
UploadToken: TypeAlias = str
FileHandle: TypeAlias = Any  # aiofiles handle
ChunkData: TypeAlias = bytes
EncryptedChunk: TypeAlias = bytes
ChunkMAC: TypeAlias = bytes
MetaMAC: TypeAlias = bytes

# More complex types
ChunkBoundary: TypeAlias = Tuple[Position, Position]
ChunkIndex: TypeAlias = int
Headers: TypeAlias = Dict[str, str]
FileAttributes: TypeAlias = Dict[str, Any]

# Result types
UploadResult: TypeAlias = Dict[str, Any]

# Protocol definitions
class LoggerProtocol(Protocol):
    """Protocol for logger objects."""
    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def critical(self, msg: str) -> None: ...

class ApiProtocol(Protocol):
    """Protocol for API objects."""
    def request(self, data: Dict[str, Any]) -> Dict[str, Any]: ... 