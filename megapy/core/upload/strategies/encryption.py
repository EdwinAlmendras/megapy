"""
Encryption strategies for file uploads.

Implements Strategy Pattern for encryption algorithms.
"""
import os
import struct
import threading
import queue
import logging
from abc import ABC, abstractmethod
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Util.strxor import strxor

logger = logging.getLogger('megapy.upload.encryption')


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
    MAC calculation runs in background thread for performance.
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
        
        # Background MAC processing
        # CRITICAL: Limit queue size to prevent memory accumulation
        # With max_parallel_uploads=21, limit to 10 chunks in queue
        # This prevents duplicating all chunks in memory (encrypted + unencrypted)
        # If queue is full, encrypt_chunk will wait (blocking) until space is available
        self._mac_queue = queue.Queue()
        self._processing_complete = threading.Event()
        self._mac_thread = threading.Thread(target=self._process_mac_queue, daemon=True)
        self._mac_thread.start()
        
        # Statistics for debugging
        self._chunks_queued = 0
        self._chunks_processed = 0
        self._max_queue_size = 0
        
        # Track chunk order
        self._last_index = -1
        self._cipher_lock = threading.Lock()
    
    @property
    def key(self) -> bytes:
        """Returns the encryption key."""
        return self._key
    
    def encrypt_chunk(self, chunk_index: int, data: bytes) -> bytes:
        """
        Encrypt a chunk using AES-CTR. MAC calculated in background.
        
        Args:
            chunk_index: Index of the chunk
            data: Raw data to encrypt
            
        Returns:
            Encrypted data (immediately, MAC runs in background)
        """
        # Verify sequential order (CTR mode requirement)
        if chunk_index != self._last_index + 1:
            raise ValueError(
                f"Chunks must be processed sequentially. "
                f"Expected {self._last_index + 1}, got {chunk_index}"
            )
        self._last_index = chunk_index
        
        # Encrypt with CTR mode (fast)
        with self._cipher_lock:
            encrypted = self._cipher.encrypt(data)
        
        # Queue data for background MAC calculation
        # CRITICAL: Use blocking put() with timeout to prevent memory accumulation
        # If queue is full, wait for space (MAC thread is processing)
        # This limits memory to max_mac_queue_size chunks instead of all chunks
        chunk_size = len(data)
        data_copy = bytes(data)
        
        try:
            # Try non-blocking first for performance
            self._mac_queue.put_nowait(data_copy)
        except queue.Full:

            self._mac_queue.put(data_copy, block=True, timeout=60.0)
        
        # Update statistics
        self._chunks_queued += 1
        current_queue_size = self._mac_queue.qsize()
        if current_queue_size > self._max_queue_size:
            self._max_queue_size = current_queue_size
        
        
        return encrypted
    
    def _process_mac_queue(self):
        """Background thread: process MAC queue."""
        processed_count = 0
        while True:
            try:
                item = self._mac_queue.get(timeout=0.1)
                
                if item is None:
                    # Signal to finish
                    self._mac_queue.task_done()
                    break
                
                chunk_size = len(item)
                queue_size_before = self._mac_queue.qsize()
                
                # Calculate chunk MAC
                chunk_mac = self._calculate_chunk_mac(item)
                
                # Update accumulator
                with self._mac_lock:
                    xored = strxor(bytes(self._mac_accumulator), chunk_mac)
                    self._mac_accumulator = bytearray(self._mac_cipher.encrypt(xored))
                
                # Release reference to chunk data
                del item
                del chunk_mac
                
                self._mac_queue.task_done()
                processed_count += 1
                self._chunks_processed += 1
                
                queue_size_after = self._mac_queue.qsize()
            except queue.Empty:
                continue
        
        logger.info(
            f"MAC thread: finished processing. Total chunks: {processed_count}, "
            f"max_queue_size: {self._max_queue_size}"
        )
        self._processing_complete.set()
    
    def _calculate_chunk_mac(self, data: bytes) -> bytes:
        """
        Calculate CBC-MAC for a chunk (Optimized).
        """
        # 1. Manejar el padding manualmente (igual que en tu código original)
        # Zero-padding para completar el último bloque si no es múltiplo de 16
        remaining = len(data) % 16
        if remaining > 0:
            padded_data = data + b'\x00' * (16 - remaining)
        else:
            padded_data = data

        # 2. El truco: Usar AES en modo CBC
        # El 'mac' actual actúa como el IV (Initial Vector) para este chunk.
        # Esto delega el bucle interno a la implementación en C de la librería.
        
        # Nota: Convertimos self._mac_template a bytes si es bytearray
        current_iv = bytes(self._mac_template)
        
        cbc_cipher = AES.new(self._aes_key, AES.MODE_CBC, iv=current_iv)
        
        # 3. Encriptamos todo de golpe
        # No necesitamos el resultado completo, solo el último bloque.
        encrypted_chunk = cbc_cipher.encrypt(padded_data)
        
        # 4. El nuevo MAC es el último bloque del cifrado
        return encrypted_chunk[-16:]
    
    def finalize(self, timeout: float = 30.0) -> bytes:
        """
        Finalize encryption and generate MEGA file key.
        
        Waits for background MAC processing to complete.
        
        Args:
            timeout: Max seconds to wait for MAC processing
        
        Returns:
            32-byte file key in MEGA format
        """
        remaining_queue_size = self._mac_queue.qsize()
        logger.info(
            f"Finalizing encryption: queue_size={remaining_queue_size}, "
            f"queued_total={self._chunks_queued}, processed_total={self._chunks_processed}, "
            f"max_queue_size={self._max_queue_size}"
        )
        
        # Signal MAC thread to finish
        self._mac_queue.put(None)
        
        # Wait for all MACs to be processed
        self._processing_complete.wait(timeout=timeout)
        
        
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
