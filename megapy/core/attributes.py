import json
import logging
from typing import Optional, Dict, Any

from Crypto.Cipher import AES
from mega_py.crypto import Base64, makestring, unmerge_key_mac, makebyte
from utils.logger import setup_logger

# Constants for key sizes
FOLDER_KEY_SIZE = 16  # Only for metadata encryption
FILE_KEY_SIZE = 24    # For content and metadata encryption

# Labels
LABEL_NAMES = ['', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'grey']

logger = setup_logger("MegaAttributes", logging.DEBUG)

class Attributes:
    """
    Class for handling MEGA node attributes encryption and decryption.
    """
    
    @staticmethod
    def decrypt(attr: str, key: bytes, logger: logging.Logger = None) -> dict:
        """
        Decrypts attributes of a MEGA node.
        
        Args:
            attr: Encrypted attributes in Base64 format
            key: Key for decryption (16 bytes for folders, 32 bytes for files)
            logger: Optional logger for debugging
        
        Returns:
            Dictionary with decrypted attributes
        
        Raises:
            ValueError: If attributes don't have a valid format
        """
        # Use only the first 16 bytes of the key for AES-CBC encryption
        key_decrypted = unmerge_key_mac(key)[:16]
        aes = AES.new(key_decrypted, AES.MODE_CBC, makebyte('\0' * 16))
        bytes_attr = aes.decrypt(Base64.decode(attr))
        
        # Convert to string and remove padding
        attr_str = makestring(bytes_attr)
        attr_str = attr_str.rstrip('\0')
        
        # Verify valid format
        if not attr_str.startswith('MEGA{"'):
            raise ValueError("MEGA NOT VALID ATTRS")
        
        # Extract JSON (skip 'MEGA' prefix)
        try:
            raw_attrs = json.loads(attr_str[4:])
            return Attributes.parse(raw_attrs)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in attributes: {e}")

    @staticmethod
    def encrypt(attr: dict, key: bytes, node_type: int) -> str:
        """
        Encrypts attributes for a MEGA node.
        
        Args:
            attr: Dictionary with attributes to encrypt
            key: Key for encryption (16 bytes for folders, 32 bytes for files)
            node_type: Node type (0=file, 1=folder)
        
        Returns:
            Base64 string with encrypted attributes
        """
        # Verify key size according to node type
        if node_type == 1 and len(key) != FOLDER_KEY_SIZE:
            logger.warning(f"Folder key should be {FOLDER_KEY_SIZE} bytes, actual: {len(key)}")
        elif node_type == 0 and len(key) != FILE_KEY_SIZE:
            logger.warning(f"File key should be {FILE_KEY_SIZE} bytes, actual: {len(key)}")
        
        # Use only the first 16 bytes of the key
        key_decrypted = unmerge_key_mac(key)[:16]
        logger.debug(f"\033[94mKey decrypted: {key_decrypted}\033[0m")
        # Prepare attributes in internal format
        
        raw_attrs = Attributes.unparse(attr)
        
        # Create AES-CBC cipher
        aes = AES.new(key_decrypted, AES.MODE_CBC, makebyte('\0' * 16))
        
        # Prepare data to encrypt with 'MEGA' prefix
        attr_bytes = makebyte('MEGA' + json.dumps(raw_attrs))
        
        # Add padding to multiple of 16 bytes
        if len(attr_bytes) % 16:
            attr_bytes += b'\0' * (16 - len(attr_bytes) % 16)
        
        # Encrypt and convert to Base64
        encrypted_attr = aes.encrypt(attr_bytes)
        return Base64.encode(encrypted_attr)

    @staticmethod
    def parse(attr: dict) -> dict:
        """
        Converts attributes from MEGA's internal format to a friendly format.
        
        Args:
            attr: Attributes in internal format
        
        Returns:
            Attributes in friendly format
        """
        return {
            "name": attr.get("n", ""),
            "label": attr.get("lbl", 0),
            "label_name": LABEL_NAMES[attr.get("lbl", 0)],
            "is_fav": bool(attr.get("fav")),
            # More attributes can be added as needed
        }

    @staticmethod
    def unparse(attr: dict) -> dict:
        """
        Converts attributes from friendly format to MEGA's internal format.
        
        Args:
            attr: Attributes in friendly format
        
        Returns:
            Attributes in MEGA's internal format
        """
        result = {
            "n": attr.get("name", "")
        }
        
        # Add optional attributes only if they exist
        if "label" in attr and attr["label"]:
            result["lbl"] = attr["label"]
        
        if attr.get("is_fav"):
            result["fav"] = 1
        
        return result

    @staticmethod
    def unpack(at: bytes) -> Optional[Dict[str, Any]]:
        """
        Extracts MEGA attributes from unencrypted bytes.
        
        The attributes are encoded as a string that starts with 'MEGA{"',
        followed by JSON data, and terminated by a null byte. This function extracts
        the string up to the null byte, verifies the 'MEGA' prefix and parses the
        JSON content.

        Args:
            at: A bytes object containing the encoded attributes.

        Returns:
            A dictionary with the parsed JSON attributes, or None if the format
            is invalid or parsing fails.

        Example:
            >>> Attributes.unpack_attributes(b'MEGA{"name":"file.txt"}\x00')
            {'name': 'file.txt'}
            >>> Attributes.unpack_attributes(b'invalid\x00')
            None
        """
        # Find the index of the first null byte (0x00)
        end = 0
        while end < len(at) and at[end] != 0:
            end += 1

        # Extract the string up to the null byte
        try:
            at_str = at[:end].decode('utf-8')
        except UnicodeDecodeError:
            return None

        # Verify 'MEGA{"' prefix
        if not at_str.startswith('MEGA{"'):
            return None

        # Parse JSON content (skip 'MEGA' prefix)
        try:
            return json.loads(at_str[4:])
        except json.JSONDecodeError:
            return None