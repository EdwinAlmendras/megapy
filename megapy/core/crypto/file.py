from Crypto.Cipher import AES
import asyncio
from typing import Tuple, Optional
from Crypto.Hash import CMAC
from Crypto.Util import Counter


def merge_key_mac(key: bytes, mac: bytes) -> bytes:
    """
    Combine encryption key and MAC.
    
    Args:
        key: Encryption key
        mac: MAC value
        
    Returns:
        Combined key and MAC
    """
    merged = key + mac
    return merged


class MegaEncrypt:
    def __init__(self, key: bytes):
        if len(key) != 24:
            raise ValueError("Key must be 24 bytes (16 AES + 8 nonce)")
        
        self.key = key
        self.aes_key = key[:16]
        self.nonce = key[16:]
        
        # Configuración CTR nativo (¡rápido en C!)
        ctr_counter = Counter.new(
            64,  # Tamaño del contador (8 bytes nonce + 8 bytes contador)
            prefix=self.nonce,
            initial_value=0,
            allow_wraparound=False
        )
        self.ctr = AES.new(
            self.aes_key,
            AES.MODE_CTR,
            counter=ctr_counter
        )
        
        # MAC usando AES-ECB nativo (rápido)
        self.mac_cipher = AES.new(self.aes_key, AES.MODE_ECB)
        self._reset_mac()
    
    def _reset_mac(self):
        self.mac = self.nonce + self.nonce  # 16 bytes
        self.mac_buffer = bytearray()
        self.pos_next = 131072  # 2^17
    
    def update_mac(self, data: bytes):
        self.mac_buffer.extend(data)
        while len(self.mac_buffer) >= 16:
            block = bytes(self.mac_buffer[:16])
            # XOR con el bloque actual
            self.mac = bytes(a ^ b for a, b in zip(self.mac, block))
            # Cifrar el MAC actual (AES-ECB)
            self.mac = self.mac_cipher.encrypt(self.mac)
            self.mac_buffer = self.mac_buffer[16:]
            
            # Lógica de bounding (cada 131KB)
            self.pos_next -= 16
            if self.pos_next <= 0:
                self.pos_next = 131072
                self._reset_mac()
    
    def encrypt(self, data: bytes) -> bytes:
        encrypted = self.ctr.encrypt(data)  # Cifrado CTR en C (rápido)
        self.update_mac(data)  # MAC sobre plaintext
        return encrypted
    
    def finalize(self) -> bytes:
        # Procesar datos residuales del MAC
        if self.mac_buffer:
            padding = bytes(16 - len(self.mac_buffer))
            self.update_mac(padding)
        
        # Condensar MAC (8 bytes finales)
        mac_condensed = self.mac[:4] + self.mac[8:12]
        return mac_condensed, self.key + mac_condensed
    
class MegaEncrypt2:
    """
    Encryption class that handles both encryption and MAC calculation.
    Can be used for both synchronous and asynchronous operations.
    """
    
    def __init__(self, key: Optional[bytes] = None, options: Optional[dict] = None):
        """
        Initialize encryption with key and options.
        
        Args:
            key: 24-byte encryption key (192-bit). If None, a random key is generated.
            options: Dictionary of options. Supported: 'start' (counter start value)
        """
        self.key = key
        self.aes_key = key[:16]
        self.nonce = key[16:]
        self.ctr = AES.new(
            self.aes_key,                   # AES key (16 bytes)
            AES.MODE_CTR,               # Modo CTR
            nonce=self.nonce,             # Nonce (8 bytes)
            initial_value=0             # Valor inicial del contador
        )
        self.cmac = CMAC.new(self.aes_key, ciphermod=AES)
        
    def encrypt(self, data: bytes) -> bytes:
        self.cmac.update(data)  
        return self.ctr.encrypt(data)  

    def finalize(self) -> Tuple[bytes, bytes]:
        mac = self.cmac.digest()
        return mac, self.key + mac

class MegaDecrypt:
    """
    Decryption class that handles both decryption and MAC verification.
    Can be used for both synchronous and asynchronous operations.
    """
    
    def __init__(self, key: bytes, options: Optional[dict] = None):
        """
        Initialize decryption with key and options.
        
        Args:
            key: 32-byte decryption key (256-bit, including MAC).
            options: Dictionary of options. Supported: 'start' (counter start value)
        """
        
        self.key = key[:24]
        self.mac = key[24:]
        self.aes_key = self.key[:16]
        self.nonce = self.key[16:]
        self.ctr = AES.new(
            self.aes_key,                   # AES key (16 bytes)
            AES.MODE_CTR,               # Modo CTR
            nonce=self.nonce,             # Nonce (8 bytes)
            initial_value=0             # Valor inicial del contador
        )
        self.cmac = CMAC.new(self.aes_key, ciphermod=AES)
        

    def decrypt(self, data: bytes) -> bytes:
        decrypted = self.ctr.decrypt(data)
        self.cmac.update(decrypted)
        return decrypted

    def finalize(self) -> bool:
        calculated_mac = self.cmac.digest()
        return calculated_mac == self.mac
    

import aiofiles
CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB

async def encrypt_file_legacy(
    input_file: str,
    output_file: str,
    key: bytes,
    chunk_size: int = CHUNK_SIZE
) -> bytes:
    """
    Encrypts a file asynchronously with legacy encryption.
    
    Args:
        input_file: Path to the file to encrypt
        output_file: Path to save the encrypted file
        key: Encryption key (24 bytes)
        chunk_size: Size of chunks for processing

    Returns:
        encryption_key_mac (merged key + mac)
    """
    
    encryptor = MegaEncrypt(key)
    loop = asyncio.get_event_loop()

    async with aiofiles.open(input_file, 'rb') as fin, \
             aiofiles.open(output_file, 'wb') as fout:
        
        while True:
            chunk = await fin.read(chunk_size)
            if not chunk:
                break
            
            # Ejecuta el cifrado en un executor para operaciones CPU-bound
            encrypted = await loop.run_in_executor(
                None,
                encryptor.encrypt,
                chunk
            )
            
            await fout.write(encrypted)

    mac, merged = encryptor.finalize()
    return merged

