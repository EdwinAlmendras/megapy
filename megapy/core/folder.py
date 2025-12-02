import os
import logging
from typing import Optional
from utils.logger import setup_logger
from mega_py.crypto import Base64, makebyte
from mega_py.attributes import  FOLDER_KEY_SIZE
from .types.folder import FolderCreatorProtocol
from .types.storage import StorageProtocol
from .file import File
from .exceptions import MegaException
from pathlib import Path
from typing import Union, Any, Dict
from mega_py.upload import MegaUploader
from mega_py.attributes import Attributes
class Folder(FolderCreatorProtocol):
    """
    Handles folder creation in MEGA
    """
    
    def __init__(self, api, storage: StorageProtocol, logger=None, log_level=logging.INFO):
        """
        Inicializa el creador de carpetas.
        
        Args:
            api: Instancia de API de MEGA
            storage: Instancia de Storage de MEGA
            logger: Logger opcional para propagación
            log_level: Nivel de log si se crea un nuevo logger
        """
        self.api = api
        self.storage: StorageProtocol = storage
        self.logger = logger or setup_logger("MegaFolderCreator", log_level)
        
    def mkdir(self, name: str, parent_id: Optional[str] = None) -> str:
        """
        Crea una nueva carpeta en MEGA.
        
        Args:
            name: Nombre de la carpeta
            parent_id: ID de la carpeta padre (opcional, por defecto raíz)
            
        Returns:
            Handle (ID) de la carpeta creada
        """
        self.logger.debug(f"Creando nueva carpeta: {name}")
        
        # Usar el ID de la carpeta raíz si no se proporciona un padre
        parent_id = parent_id
        
        if parent_id is None:
            raise ValueError("No se especificó la carpeta padre y no hay carpeta raíz")
            
        # Generar una clave aleatoria para la carpeta
        folder_key = os.urandom(FOLDER_KEY_SIZE)
        
        if len(folder_key) != FOLDER_KEY_SIZE:
            raise ValueError(f"La clave de carpeta debe ser de {FOLDER_KEY_SIZE} bytes")
            
        # Crear atributos de la carpeta
        attributes = {'name': name}
        
        # Cifrar la clave de la carpeta con la clave maestra
        encrypted_key = self.storage._encrypt_key(folder_key)

        
        # Cifrar los atributos con la clave de la carpeta
        encrypted_attrs = Attributes.encrypt(attributes, folder_key, 1)  # 1 = carpeta
        
        # Crear el nodo
        response = self.api.request({
            'a': 'p',  # put (añadir nodo)
            't': parent_id,  # target (padre)
            'n': [{  # node
                'h': 'xxxxxxxx',  # placeholder
                't': 1,  # type (1 = carpeta)
                'a': encrypted_attrs,  # attributes
                'k': Base64.encode(encrypted_key)  # key
            }]
        })
        
        if 'f' not in response or not response['f'] or 'h' not in response['f'][0]:
            raise ValueError("Respuesta inválida del servidor al crear la carpeta")
            
        # Obtener el handle del nuevo nodo
        folder_handle = response['f'][0]['h']
        
        self.logger.info(f"Carpeta creada exitosamente: {name} (handle: {folder_handle})")
        return folder_handle
        
    async def upload(
        self, 
        file_path: Union[str, Path], 
        parent: Optional[str] = None, 
        name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        use_chunked_upload: bool = False,
        progress_callback = None,
        **kwargs: Any
    ) -> File:
        """
        Upload a file to MEGA.
        
        Args:
            file_path: Path to local file
            parent: Parent folder ID (defaults to root)
            name: Custom filename (defaults to original filename)
            attributes: Additional file attributes
            use_chunked_upload: Whether to use chunked upload for large files
            
        Returns:
            File object for the uploaded file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            MegaException: If upload fails
            
        Examples:
            >>> storage = Storage(email="user@example.com", password="password")
            >>> file = storage.upload_file("document.pdf")
            >>> print(f"Uploaded {file.name} ({file.size} bytes)")
        """
        self.logger.debug(f"Starting file upload: {file_path}")
        
        # Convert to Path if string
        if isinstance(file_path, str):
            file_path = Path(file_path)
            
        # Verify file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Use root folder if parent not specified
        parent_id = parent or self.root_id
        if not parent_id:
            raise MegaException("No parent folder specified and root folder not available")
            
        # Use original filename if name not specified
        name = name or file_path.name
        
        # Create attributes if not provided
        if attributes is None:
            attributes = {}
        
        # Add name to attributes
        attributes["name"] = name
        
        # Select appropriate upload strategy
        
        # Create uploader instance
        uploader = MegaUploader(
            api=self.api,
            master_key=self.storage.key,
        )
        

        return await uploader.upload(
            target_folder_id=parent_id,
            file_path=file_path,
            attributes=attributes,
            encryption_key=None,
            max_concurrent_uploads=4,
            **kwargs
        )
            
  
            