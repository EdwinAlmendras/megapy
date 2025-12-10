"""
Crypto request builder for MEGA API.

This module provides functionality to create crypto request arrays
for sharing files and folders, similar to makeCryptoRequest in mega.js.

Source: https://github.com/meganz/webclient/blob/918222d5e4521c8777b1c8da528f79e0110c1798/js/crypto.js#L3728
"""
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ...node import Node

from .aes import AESCrypto
from .utils.encoding import Base64Encoder


def make_crypto_request(
    share_keys: Dict[str, bytes],
    sources: Union['Node', List['Node']],
    shares: Optional[List[str]] = None
) -> List[Any]:
    """
    Generate crypto request array for the given nodes/shares matrix.
    
    This function creates a crypto request array that is used in MEGA API calls
    to share files and folders. The array format is:
    [shares, nodes, keys]
    
    Where:
    - shares: List of share handles
    - nodes: List of node IDs (handles)
    - keys: Flat array of [share_index, node_index, encrypted_key, ...]
    
    Args:
        share_keys: Dictionary mapping share handles to their encryption keys
        sources: Node object or list of Node objects. If a single Node, 
                 it will include itself and all children recursively.
        shares: Optional list of share handles. If not provided, will use
                the node's shares property (shares from node and parents)
    
    Returns:
        Crypto request array: [shares, nodes, keys]
        
    Example:
        >>> folder = mega.get_node("folder_handle")
        >>> share_keys = node_service.share_keys
        >>> cr = make_crypto_request(share_keys, folder)
        >>> # Returns: [['share_handle'], ['node1'], [0, 0, 'encrypted_key_base64']]
    """
    encoder = Base64Encoder()
    
    # Normalize sources to a list of Node objects
    if not isinstance(sources, list):
        # Single Node - get self and all children
        if hasattr(sources, 'self_and_children'):
            nodes = sources.self_and_children
        else:
            nodes = [sources]
    else:
        # List of Nodes
        nodes = sources
    
    # Filter nodes that have keys
    nodes = [node for node in nodes if node.key]
    
    # Sort nodes: files (type 0) first, then folders (type 1)
    # However, if a node's handle is in shares, it should come first (the folder being shared)
    # This matches the order in mega.js where the shared folder appears first in nodes
    nodes.sort(key=lambda n: (
        0 if n.handle in shares else (1 if n.is_folder else 0),  # Share folder first, then files, then other folders
        n.handle
    ))
    
    # If shares not provided, determine them from nodes
    if shares is None:
        shares = []
        for node in nodes:
            node_shares = node.shares
            for share in node_shares:
                if share not in shares:
                    shares.append(share)
    
    # Build crypto request structure
    # Note: The folder being shared will appear in both shares and nodes (this is correct per mega.js)
    crypto_request = [
        shares,  # List of share handles
        [node.handle for node in nodes],  # Node handles (includes the folder if it's in self_and_children)
        []  # Keys array (will be populated)
    ]
    
    # Encrypt each node key with each share key
    for i, share_handle in enumerate(shares):
        if share_handle not in share_keys:
            continue
            
        share_key = share_keys[share_handle]
        
        # Skip if share_key is empty bytes (b'') or None (placeholder - share exists but key not available)
        # This happens when ok0/ok contains placeholder data
        # Empty bytes (b'') means share exists but key unavailable, None means not processed
        if not share_key or (isinstance(share_key, bytes) and len(share_key) == 0):
            continue
            
        aes = AESCrypto(share_key)
        
        for j, node in enumerate(nodes):
            
            file_key = node.key
            if not file_key:
                continue
            
            # In mega.js: if fileKey.length === 32 || fileKey.length === 16, encrypt directly
            # For 32-byte keys (files with MAC), encrypt the full 32 bytes
            # For 16-byte keys (folders), encrypt the 16 bytes
            # AES-ECB can handle multiples of 16 bytes (32 bytes = 2 blocks)
            if len(file_key) == 32 or len(file_key) == 16:
                # Encrypt the full key directly (32 bytes for files, 16 bytes for folders)
                encrypted_key = aes.encrypt_ecb(file_key)
            else:
                # For other lengths, pad to 16 bytes
                if len(file_key) < 16:
                    padded_key = file_key + b'\x00' * (16 - len(file_key))
                else:
                    # Truncate to 16 bytes if longer than 32
                    padded_key = file_key[:16]
                encrypted_key = aes.encrypt_ecb(padded_key)
            
            encrypted_key_b64 = encoder.encode(encrypted_key)
            
            # Add to keys array: [share_index, node_index, encrypted_key]
            crypto_request[2].extend([i, j, encrypted_key_b64])
    
    return crypto_request

