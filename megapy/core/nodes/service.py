"""Node loading and tree building service."""
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from .decryptor import KeyDecryptor
from ...node import Node
from ..attributes.models import FileAttributes
from ..crypto import AESCrypto, Base64Encoder
from megapy.core.logging import get_logger
import logging
logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from ...client import MegaClient


class NodeService:
    """
    Single service for loading and managing MEGA nodes.
    
    Responsibilities:
    - Load nodes from API
    - Decrypt keys and attributes
    - Build node tree with parent/child relationships
    - Process and store share keys from response.ok
    """
    
    NODE_TYPE_FILE = 0
    NODE_TYPE_FOLDER = 1
    NODE_TYPE_ROOT = 2
    NODE_TYPE_INBOX = 3
    NODE_TYPE_TRASH = 4
    
    def __init__(self, master_key: bytes, client: 'MegaClient' = None):
        self._master_key = master_key
        self._client = client
        self._decryptor = KeyDecryptor()
        
        self._nodes: Dict[str, Node] = {}
        self._root: Optional[Node] = None
        self._root_handle: Optional[str] = None
        self._share_keys: Dict[str, bytes] = {}  # Share keys from response.ok
    
    @property
    def root(self) -> Optional[Node]:
        return self._root
    
    @property
    def root_handle(self) -> Optional[str]:
        return self._root_handle
    
    @property
    def nodes(self) -> Dict[str, Node]:
        return self._nodes
    
    @property
    def share_keys(self) -> Dict[str, bytes]:
        """Get share keys dictionary (like storage.shareKeys in mega.js)."""
        return self._share_keys
    
    def load(self, api_response: Dict[str, Any]) -> Node:
        """
        Load nodes from API response and build tree.
        
        Also processes share keys from response.ok (like mega.js storage.reload).
        
        Returns:
            Root node with full hierarchy
        """
        logger.debug("Starting NodeService.load()")
        nodes_data = api_response.get('f', [])
        logger.debug(f"Number of nodes in API response: {len(nodes_data)}")

        self._nodes.clear()
        self._root = None

        # Process share keys from response.ok (like mega.js)
        logger.debug("Processing share keys with _process_share_keys()")
        self._process_share_keys(api_response)

        # First pass: create all nodes
        logger.debug("First pass: creating all nodes")
        for idx, data in enumerate(nodes_data, 1):
            node = self._create_node(data)
            if node:
                self._nodes[node.handle] = node

        # Second pass: build parent/child relationships
        logger.debug("Second pass: building parent/child relationships")
        for idx, data in enumerate(nodes_data, 1):
            handle = data.get('h')
            parent_handle = data.get('p')

            if handle not in self._nodes:
                logger.warning(f"Node with handle '{handle}' not found in _nodes. Skipping relationship assignment.")
                continue

            node = self._nodes[handle]

            if parent_handle and parent_handle in self._nodes:
                parent = self._nodes[parent_handle]
                node.parent = parent
                if node not in parent.children:
                    parent.children.append(node)

        logger.debug("Node loading complete. Returning root node.")
        return self._root

    def _process_share_keys(self, api_response: Dict[str, Any]) -> None:
        """
        Processes share keys from response.ok, similar to mega.js storage.reload.

        Source: https://github.com/qgustavor/mega/blob/master/lib/storage.mjs#L152

        This processes the 'ok' field from the API response which contains share data.
        For each share, it verifies authenticity and decrypts the share key, with detailed logging.

        Args:
            api_response: API response containing 'ok' field with share data
        """
        import json

        encoder = Base64Encoder()
        aes = AESCrypto(self._master_key)
        
        # Process ok0 (streaming format) or ok (legacy/cached format)
        # ok0 is processed element by element in streaming, ok is processed all at once
        # If ok0 exists, it means we're in streaming mode and ok elements come separately
        # If only ok exists, it's legacy cached format
        ok_list = []
        has_ok0 = bool(api_response.get('ok0'))
        has_ok = bool(api_response.get('ok'))
        
        if has_ok0:
            # ok0 is a dict where keys are handlers and values are share data
            # Convert to list format for consistent processing
            # When ok0 exists, we're in streaming mode - preserve existing share keys
            logger.debug("Processing ok0 (streaming mode)")
            ok0_dict = api_response.get('ok0')
            if isinstance(ok0_dict, dict):
                ok_list = [{'h': handler, **data} for handler, data in ok0_dict.items()]
            else:
                ok_list = ok0_dict if isinstance(ok0_dict, list) else []
            # Don't reset share_keys for ok0 - preserve existing ones (streaming mode)
            if not self._share_keys:
                self._share_keys = {}
            logger.debug(f"Processing ok0 (streaming mode) - preserving existing {len(self._share_keys)} share keys")
        elif has_ok:
            # Legacy format - process all at once
            # When only ok exists (no ok0), reset share keys (legacy cached format)
            ok_list = api_response.get('ok')
            if not isinstance(ok_list, list):
                ok_list = []
            self._share_keys = {}
            logger.debug("Processing ok (legacy format) - resetting share keys")
        else:
            # No ok or ok0 - only reset if we don't have any share keys yet
            if not self._share_keys:
                self._share_keys = {}
            logger.debug("No 'ok' or 'ok0' key found in api_response. Preserving existing share keys.")
            return
        
        if not ok_list:
            logger.debug("No share keys to process (empty 'ok' or 'ok0' data).")
            return
        
        for idx, share in enumerate(ok_list, 1):
            handler = share.get('h')
            logger.debug(f"Processing share {idx} with handler: {handler}")
            if not handler:
                logger.warning(f"Share entry {idx} does not contain a handler ('h'). Skipping.")
                continue

            logger.debug(f"Processing share {idx} with handler: {handler}")

            share_ha = share.get('ha')
            share_k = share.get('k')
            logger.debug(f"Share {idx} 'ha': {share_ha}, 'k': {share_k}")
            if not share_ha or not share_k:
                logger.warning(f"Share {idx} (handler {handler}) missing 'ha' or 'k'. Skipping.")
                continue

            # Check if ha and k are placeholder values (all A's or zeros)
            # When placeholders are present, it means the share exists but we don't have the key yet
            # In webclient, when ok0 has placeholders, crypto_handleauthcheck fails and sharekey is not stored
            # But the share still exists, so we should mark it to use placeholders in s2 requests
            # We store a special marker (empty bytes or None) to indicate share exists but key unavailable
            if share_ha == "AAAAAAAAAAAAAAAAAAAAAA" or share_k == "AAAAAAAAAAAAAAAAAAAAAA":
                logger.debug(f"Share {idx} (handler {handler}) has placeholder data. Share exists but key not available - will use placeholders in s2 requests.")
                # Store a special marker to indicate share exists (for detection) but key is not available
                # This is different from not having the share at all
                # We use an empty bytes object as marker (not None, to distinguish from "not processed")
                self._share_keys[handler] = b''  # Empty bytes = share exists but key unavailable (placeholder)
                continue

            logger.debug(f"Share {idx} 'ha': {share_ha}, 'k': {share_k}")

            handler_bytes = handler.encode('utf-8')
            auth = aes.encrypt_ecb(handler_bytes + handler_bytes)
            logger.debug(f"Auth value for handler '{handler}': {auth.hex()}")

            share_ha_bytes = encoder.decode(share_ha) if isinstance(share_ha, str) else share_ha

            # Constant time compare to prevent timing attacks
            if self._constant_time_compare(share_ha_bytes, auth):
                logger.debug(f"Auth hash matches for share handler {handler}. Proceeding to decrypt share key.")
                share_k_bytes = encoder.decode(share_k) if isinstance(share_k, str) else share_k
                decrypted_key = aes.decrypt_ecb(share_k_bytes)
                self._share_keys[handler] = decrypted_key
                logger.info(f"Share key for handler '{handler}' successfully decrypted and stored.")
            else:
                logger.warning(
                    f"Auth hash does not match for share handler {handler}. Skipping decryption."
                )
                continue
    def _constant_time_compare(self, a: bytes, b: bytes) -> bool:
        """
        Constant time comparison to prevent timing attacks.
        
        Source: https://github.com/qgustavor/mega/blob/master/lib/crypto/index.mjs#L156
        
        Args:
            a: First bytes to compare
            b: Second bytes to compare
            
        Returns:
            True if equal, False otherwise
        """
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= x ^ y
        
        return result == 0
    
    def _create_node(self, data: Dict[str, Any]) -> Optional[Node]:
        """Create a single node from API data."""
        try:
            handle = data.get('h', '')
            node_type = data.get('t', 0)
            
            # Skip inbox and trash
            if node_type in (self.NODE_TYPE_INBOX, self.NODE_TYPE_TRASH):
                return None
            
            # Decrypt key (full 32 bytes for files)
            # Pass share_keys to handle shared nodes with multiple id:key pairs
            key = self._decryptor.decrypt_node_key(data, self._master_key, self._share_keys)
            
            # Decrypt attributes
            attrs = self._decryptor.decrypt_attributes(data, key)
            
            name = attrs.get('n', handle)
            
            # Handle root folder
            if node_type == self.NODE_TYPE_ROOT:
                name = "Cloud Drive"
                self._root_handle = handle
            
            node = Node(
                handle=handle,
                name=name,
                size=data.get('s', 0),
                is_folder=(node_type in (self.NODE_TYPE_FOLDER, self.NODE_TYPE_ROOT)),
                parent_handle=data.get('p'),
                key=key,
                fa=data.get('fa'),
                attributes=FileAttributes.from_dict(attrs),
                _client=self._client,
                _raw=data
            )

            
            if node_type == self.NODE_TYPE_ROOT:
                self._root = node
            
            return node
        except Exception:
            return None
    
    def get(self, handle: str) -> Optional[Node]:
        """Get node by handle."""
        return self._nodes.get(handle)
    
    def find_by_name(self, name: str) -> Optional[Node]:
        """Find first node matching name."""
        for node in self._nodes.values():
            if node.name == name:
                return node
        return None
    
    def find_by_path(self, path: str) -> Optional[Node]:
        """Find node by path from root."""
        if not self._root or not path:
            return self._root
        
        if path == "/":
            return self._root
        
        return self._root.find(path.lstrip("/"))
    
    def all_files(self) -> List[Node]:
        """Get all files (flat list)."""
        return [n for n in self._nodes.values() if n.is_file]
    
    def all_folders(self) -> List[Node]:
        """Get all folders (flat list)."""
        return [n for n in self._nodes.values() if n.is_folder]
    
    def add_node(self, node: Node) -> None:
        """
        Add a node to the tree and update parent-child relationships.
        
        This method should be called after creating a new node (via create_folder,
        upload, etc.) to ensure it's properly integrated into the tree structure.
        
        Args:
            node: Node to add to the tree
        """
        if not node or not node.handle:
            return
        
        # Add to nodes dictionary
        self._nodes[node.handle] = node
        
        # Update parent-child relationship if parent exists
        if node.parent_handle:
            parent_node = self._nodes.get(node.parent_handle)
            if parent_node:
                node.parent = parent_node
                if node not in parent_node.children:
                    parent_node.children.append(node)