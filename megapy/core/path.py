from pathlib import PurePath
from typing import Callable, Optional, Union, List, Iterator, Any, Dict
import os

from mega_py.storage import Storage
from mega_py.file import File
from mega_py.mutable_file import MutableFile
from mega_py.types.storage import StorageProtocol


class MegaPath:
    """Pathlib-like interface for MEGA storage navigation."""

    def __init__(self, storage: Storage, path: str = "/"):
        """
        Initialize a MEGA path object.

        Args:
            storage: The MEGA storage client
            path: Path string (defaults to root "/")
        """
        self.storage: StorageProtocol = storage
        self._path = path.strip("/")
        self._file_obj: MutableFile = {}
        self._resolve()

    def _resolve(self):
        """Resolve the path to a file/folder object"""
        if not self._path:
            # Root directory
            self._file_obj = self.storage.get_file(self.storage.ROOT_ID)
            return

        # Navigate through path components
        parts = self._path.split("/")
        current_id = self.storage.ROOT_ID

        for part in parts:
            found = False
            for file in self.storage.list_files(current_id):
                if file.name == part:
                    current_id = file.handle
                    self._file_obj = file
                    found = True
                    break

            if not found:
                raise FileNotFoundError(f"Path not found: {self._path}")

    def __truediv__(self, other: str) -> "MegaPath":
        """
        Support for path / operator.

        Args:
            other: Path component to append

        Returns:
            New MegaPath object
        """
        if not isinstance(other, str):
            raise TypeError("Path component must be a string")

        new_path = f"{self._path}/{other}" if self._path else other
        return MegaPath(self.storage, new_path)

    def __str__(self) -> str:
        """String representation of the path"""
        return f"/{self._path}"

    def __repr__(self) -> str:
        """Formal representation of the path"""
        return f"MegaPath('{self}')"

    @property
    def name(self) -> str:
        """Name of the file or folder"""
        if not self._path:
            return ""
        return os.path.basename(self._path)

    @property
    def parent(self) -> "MegaPath":
        """Parent directory"""
        if not self._path:
            return self  # Root has itself as parent

        parent_path = os.path.dirname(self._path)
        return MegaPath(self.storage, parent_path)

    @property
    def parts(self) -> tuple:
        """Path components as a tuple"""
        if not self._path:
            return ("/",)
        return tuple([""] + self._path.split("/"))

    @property
    def is_dir(self) -> bool:
        """Check if the path points to a directory"""
        return self._file_obj and getattr(self._file_obj, "is_dir", False)

    @property
    def is_file(self) -> bool:
        """Check if the path points to a file"""
        return self._file_obj and not getattr(self._file_obj, "is_dir", True)

    @property
    def size(self) -> int:
        """Size of the file in bytes"""
        if not self._file_obj:
            return 0
        return getattr(self._file_obj, "size", 0)

    @property
    def timestamp(self) -> int:
        """Creation timestamp of the file or folder"""
        if not self._file_obj:
            return 0
        return getattr(self._file_obj, "creation_date", 0)

    @property
    def handle(self) -> str:
        """Get the MEGA handle for this path"""
        if not self._file_obj:
            return ""
        return self._file_obj.handle

    def exists(self) -> bool:
        """Check if the path exists"""
        return self._file_obj is not None

    def iterdir(self) -> Iterator["MegaPath"]:
        """
        Iterate over the files in a directory.

        Yields:
            MegaPath objects for each child
        """
        if not self._file_obj.is_dir:
            raise NotADirectoryError(f"Not a directory: {self}")

        for file in self._file_obj.list():
            child_path = f"{self._path}/{file.name}" if self._path else file.name
            yield MegaPath(self.storage, child_path)

    def get_attributes(self) -> Dict[str, Any]:
        """Get file/folder attributes"""
        if not self._file_obj:
            return {}
        return getattr(self._file_obj, "attributes", {})

    def download(self, target_path: str = None) -> str:
        """
        Download the file to the local filesystem.

        Args:
            target_path: Local path to save the file (defaults to current dir with same name)

        Returns:
            Path to the downloaded file
        """
        if not self._file_obj or self.is_dir:
            raise ValueError("Cannot download a directory or non-existent file")

        return self._file_obj.download(target_path)

    def delete(self, permanent: bool = False) -> bool:
        """
        Delete the file or directory.

        Args:
            permanent: If True, permanently delete instead of moving to trash

        Returns:
            True if successful
        """
        if not self._file_obj:
            raise FileNotFoundError(f"Path not found: {self}")

        return self.storage.delete(self._file_obj.handle, permanent)

    async def upload(
        self,
        file_path: str,
        name: str = None,
        attributes: Dict[str, Any] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Upload a file to the path.

        Args:
            file_path: Path to the local file
            name: Name of the file in MEGA (defaults to original filename)
            attributes: Additional file attributes
            progress_callback: Optional callback function to report progress,
                              receives (bytes_uploaded, total_bytes)
        Returns:
            None
        """
        return await self._file_obj.upload(
            file_path=file_path,
            name=name,
            attributes=attributes,
            progress_callback=progress_callback,
            **kwargs
        )


class MegaRoot(MegaPath):
    """Root directory in MEGA storage."""

    def __init__(self, storage: Storage):
        """Initialize with root path"""
        super().__init__(storage, "/")


class MegaHome(MegaPath):
    """User's home directory in MEGA."""

    def __init__(self, storage: Storage):
        """Initialize with root path"""
        super().__init__(storage, "/")


# Extend Storage class with pathlib-like functionality
def extend_storage():
    """Add pathlib-like methods to Storage class"""

    def Path(self, path: str = "/") -> MegaPath:
        """
        Create a pathlib-like object for MEGA storage navigation.

        Args:
            path: Path string (defaults to root "/")

        Returns:
            MegaPath object
        """
        return MegaPath(self, path)

    def Root(self) -> MegaRoot:
        """
        Get the root directory.

        Returns:
            MegaRoot object
        """
        return MegaRoot(self)

    def Home(self) -> MegaHome:
        """
        Get the user's home directory.

        Returns:
            MegaHome object
        """
        return MegaHome(self)

    # Add methods to Storage class
    Storage.Path = Path
    Storage.Root = Root
    Storage.Home = Home

    return Storage


# Auto-extend Storage class when imported
extend_storage()
