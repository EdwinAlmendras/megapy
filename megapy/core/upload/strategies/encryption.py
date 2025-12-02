"""
Encryption strategies for file uploads.

Implements Strategy Pattern for encryption algorithms.
"""
import os
import struct
import threading
from abc import ABC, abstractmethod
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Util.strxor import strxor


class BaseEncryptionStrategy(ABC):
    """Abstract base class for encryption strategies."""
    
    @abstractmethod
    def encrypt_chunk(self, chunk_index: int, data: bytes) -> bytes:
        """Encrypt a chunk of data."""
        pass
    
    @abstractmethod
    def finalize(self) -> bytes:
        """Finalize encryption and return the file key."""
        pass
    
    @property
    @abstractmethod
    def key(self) -> bytes:
        """Returns the encryption key."""
        pass


class MegaEncryptionStrategy(BaseEncryptionStrategy):
    """
    MEGA's AES-CTR encryption with CBC-MAC.
    
    Uses AES-CTR for encryption and CBC-MAC for integrity.
    Thread-safe implementation with optimized MAC calculation.
    """
    
    AES_BLOCK_SIZE = 16
    KEY_SIZE = 24  # 16 bytes AES key + 8 bytes nonce
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize encryption strategy.
        
        Args:
            encryption_key: Optional 24-byte key (16 AES + 8 nonce).
                          If not provided, a random key is generated.
        """
        self._key = encryption_key or os.urandom(self.KEY_SIZE)
        
        if len(self._key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")
        
        self._aes_key = self._key[:16]
        self._nonce = self._key[16:24]
        
        # CTR cipher for encryption
        ctr = Counter.new(
            64,
            prefix=self._nonce,
            initial_value=0,
            little_endian=False
        )
        self._cipher = AES.new(self._aes_key, AES.MODE_CTR, counter=ctr)
        
        # ECB cipher for MAC calculation
        self._mac_cipher = AES.new(self._aes_key, AES.MODE_ECB)
        
        # Initial MAC value: h := (nonce << 64) | nonce
        n = int.from_bytes(self._nonce, byteorder='big')
        h = (n << 64) | n
        self._mac_template = h.to_bytes(16, byteorder='big')
        
        # MAC accumulator
        self._mac_accumulator = bytearray(16)
        self._mac_lock = threading.Lock()
        
        # Track chunk order
        self._last_index = -1
        self._cipher_lock = threading.Lock()
    
    @property
    def key(self) -> bytes:
        """Returns the encryption key."""
        return self._key
    
    def encrypt_chunk(self, chunk_index: int, data: bytes) -> bytes:
        """
        Encrypt a chunk using AES-CTR and update MAC.
        
        Args:
            chunk_index: Index of the chunk
            data: Raw data to encrypt
            
        Returns:
            Encrypted data
        """
        # Verify sequential order (CTR mode requirement)
        if chunk_index != self._last_index + 1:
            raise ValueError(
                f"Chunks must be processed sequentially. "
                f"Expected {self._last_index + 1}, got {chunk_index}"
            )
        self._last_index = chunk_index
        
        # Encrypt with CTR mode
        with self._cipher_lock:
            encrypted = self._cipher.encrypt(data)
        
        # Calculate and accumulate MAC
        chunk_mac = self._calculate_chunk_mac(data)
        with self._mac_lock:
            xored = strxor(bytes(self._mac_accumulator), chunk_mac)
            self._mac_accumulator = bytearray(self._mac_cipher.encrypt(xored))
        
        return encrypted
    
    def _calculate_chunk_mac(self, data: bytes) -> bytes:
        """
        Calculate CBC-MAC for a chunk.
        
        Args:
            data: Chunk data
            
        Returns:
            16-byte MAC
        """
        mac = bytearray(self._mac_template)
        
        # Process complete blocks
        full_blocks = len(data) - (len(data) % 16)
        for i in range(0, full_blocks, 16):
            block = data[i:i+16]
            xored = strxor(bytes(mac), block)
            mac = bytearray(self._mac_cipher.encrypt(xored))
        
        # Process remaining bytes with padding
        remaining = len(data) % 16
        if remaining > 0:
            last_block = data[full_blocks:] + b'\x00' * (16 - remaining)
            xored = strxor(bytes(mac), last_block)
            mac = bytearray(self._mac_cipher.encrypt(xored))
        
        return bytes(mac)
    
    def finalize(self) -> bytes:
        """
        Finalize encryption and generate MEGA file key.
        
        Returns:
            32-byte file key in MEGA format
        """
        # Calculate meta-MAC
        with self._mac_lock:
            mac_data = bytes(self._mac_accumulator)
        
        parts = struct.unpack(">IIII", mac_data)
        meta_mac_high = parts[0] ^ parts[1]
        meta_mac_low = parts[2] ^ parts[3]
        meta_mac = struct.pack(">II", meta_mac_high, meta_mac_low)
        
        # Create MEGA key format
        return self._create_mega_key(meta_mac)
    
    def _create_mega_key(self, meta_mac: bytes) -> bytes:
        """
        Create MEGA file key format.
        
        Args:
            meta_mac: 8-byte meta MAC
            
        Returns:
            32-byte MEGA file key
        """
        key_parts = struct.unpack(">IIII", self._aes_key)
        nonce_parts = struct.unpack(">II", self._nonce)
        meta_parts = struct.unpack(">II", meta_mac)
        
        return struct.pack(
            ">IIIIIIII",
            key_parts[0] ^ nonce_parts[0],
            key_parts[1] ^ nonce_parts[1],
            key_parts[2] ^ meta_parts[0],
            key_parts[3] ^ meta_parts[1],
            nonce_parts[0],
            nonce_parts[1],
            meta_parts[0],
            meta_parts[1]
        )
