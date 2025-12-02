import os
from mega_py.types.file import MutableFileProtocol
from .file import File
from utils.logger import setup_logger
import logging


class MutableFile(File, MutableFileProtocol):
    """
    MEGA folder representation

    Extends File with folder-specific operations
    """

    def __init__(self, storage, *args, **kwargs):
        super().__init__(storage, *args, **kwargs)
        self.storage = storage
        self.logger = setup_logger("MutableFile", logging.DEBUG)

    def list(self):
        """
        List files in this folder

        Returns:
            List of File objects
        """
        if not self.is_dir:
            raise NotADirectoryError(f"Not a directory: {self}")
        return self.storage.list_files(self.handle)

    def mkdir(self, name):
        """
        Create a subfolder

        Args:
            name: Folder name

        Returns:
            MutableFile object for the created folder
        """
        return self.storage.mkdir(name, self.handle)

    async def upload(
        self,
        file_path,
        name=None,
        attributes=None,
        progress_callback=None,
        **kwargs,
    ):
        """
        Upload a file to this folder

        Args:
            file_path: Path to local file
            name: Custom name (defaults to original filename)
            progress_callback: Optional callback function to report progress,
                              receives (bytes_uploaded, total_bytes)
        Returns:
            File object for the uploaded file
        """
        self.logger.info(f"\033[94mColor\033[0m")
        return await self.storage.upload(
            file_path=file_path,
            parent=self.handle,
            name=name,
            attributes=attributes,
            progress_callback=progress_callback,
            **kwargs,
        )

    def get_file(self, name):
        """
        Get a file by name

        Args:
            name: File name

        Returns:
            File or MutableFile object
        """
        for file in self.list_files():
            if file.name == name:
                return file

        raise ValueError(f"File not found: {name}")

    def download(self, path=None):
        """
        Download folder contents

        Args:
            path: Local folder path (defaults to current directory with folder name)

        Returns:
            Downloaded folder path
        """
        if path is None:
            path = self.name

        # Ensure directory exists
        os.makedirs(path, exist_ok=True)

        # Download all files
        for file in self.storage.list_files(self.handle):
            if isinstance(file, MutableFile):
                # Recursively download subfolders
                subfolder_path = os.path.join(path, file.name)
                file.download(subfolder_path)
            else:
                # Download file
                file.download(path)

        return path
