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

class MegaDecrypt:
    """
    Decryption class that handles both decryption and MAC verification.
    Can be used for both synchronous and asynchronous operations.
    """
    
    def __init__(self, key: bytes, options: Optional[dict] = None):
        """
        Initialize decryption with key and options.
        
        Args:
            key: 32-byte decryption key (256-bit, including MAC) or 24-byte key (without MAC).
            options: Dictionary of options. Supported: 
                - 'start' or 'initial_value': Counter start value (default: 0)
                - 'position': Byte position in file (will calculate initial_value = position // 16)
        """
        options = options or {}
        
        # Handle both 24-byte and 32-byte keys
        if len(key) >= 32:
            self.key = key[:24]
            self.mac = key[24:32]
        elif len(key) >= 24:
            self.key = key[:24]
            self.mac = key[24:] if len(key) > 24 else None
        else:
            raise ValueError(f"Key too short: {len(key)} bytes, need at least 24")
        
        self.aes_key = self.key[:16]
        self.nonce = self.key[16:]
        
        # Get initial counter value from options
        if 'position' in options:
            position = options['position']
            initial_value = position // 16
            self._position = position  # Track exact position for partial block handling
        elif 'start' in options:
            initial_value = options['start']
            self._position = initial_value * 16
        elif 'initial_value' in options:
            initial_value = options['initial_value']
            self._position = initial_value * 16
        else:
            initial_value = 0
            self._position = 0
        
        # Create counter using Counter.new() for proper CTR mode
        ctr_counter = Counter.new(
            64,  # Counter size (64 bits for the counter part)
            prefix=self.nonce,  # 8-byte prefix (nonce)
            initial_value=initial_value,  # Starting counter value
            allow_wraparound=False
        )
        
        self.ctr = AES.new(
            self.aes_key,  # AES key (16 bytes)
            AES.MODE_CTR,
            counter=ctr_counter
        )
        
        # Handle partial block offset if position is not aligned to 16-byte boundary
        if 'position' in options:
            offset_in_block = position % 16
            if offset_in_block > 0:
                # Decrypt and discard bytes before desired offset
                self.ctr.decrypt(b'\x00' * offset_in_block)
        
        # Only initialize CMAC if we have a MAC to verify
        self.cmac = CMAC.new(self.aes_key, ciphermod=AES) if self.mac else None
        

    def decrypt(self, data: bytes, position: Optional[int] = None) -> bytes:
        """
        Decrypt data chunk.
        
        Args:
            data: Encrypted data to decrypt
            position: Optional byte position in file (for handling partial blocks)
            
        Returns:
            Decrypted data
        """
        # If position is provided and different from current, handle partial block offset
        if position is not None and position != self._position:
            offset_in_block = position % 16
            if offset_in_block > 0:
                # Need to decrypt and discard bytes before desired offset
                # Recreate cipher with correct initial value
                block_num = position // 16
                ctr_counter = Counter.new(
                    64,
                    prefix=self.nonce,
                    initial_value=block_num,
                    allow_wraparound=False
                )
                self.ctr = AES.new(self.aes_key, AES.MODE_CTR, counter=ctr_counter)
                # Decrypt and discard padding
                self.ctr.decrypt(b'\x00' * offset_in_block)
                self._position = position
        
        decrypted = self.ctr.decrypt(data)
        self._position += len(data)
        
        # Update MAC if we have one
        if self.cmac:
            self.cmac.update(decrypted)
        
        return decrypted

    def finalize(self) -> bool:
        """Verify MAC if available."""
        if not self.mac or not self.cmac:
            return True  # No MAC to verify
        
        calculated_mac = self.cmac.digest()
        # MAC condensado: primeros 4 bytes + bytes 8-12
        mac_condensed = calculated_mac[:4] + calculated_mac[8:12]
        return mac_condensed == self.mac


def test_encrypt_decrypt_pipeline():
    """
    Test rápido para verificar que encriptación y desencriptación funcionan correctamente.
    Genera 1MB de datos aleatorios, los encripta y luego los desencripta.
    """
    import os
    
    # Generar 1MB de datos aleatorios
    data_size = 1024 * 1024  # 1MB
    original_data = os.urandom(data_size)
    
    # Crear clave de 24 bytes (16 AES + 8 nonce)
    key = os.urandom(24)
    
    print(f"Test: Encriptando {data_size} bytes...")
    
    # Encriptar
    encryptor = MegaEncrypt(key)
    encrypted_data = encryptor.encrypt(original_data)
    mac_condensed, full_key = encryptor.finalize()
    
    print(f"  - Datos originales: {len(original_data)} bytes")
    print(f"  - Datos encriptados: {len(encrypted_data)} bytes")
    print(f"  - MAC: {mac_condensed.hex()}")
    print(f"  - Full key: {len(full_key)} bytes")
    
    # Desencriptar
    print(f"Test: Desencriptando {len(encrypted_data)} bytes...")
    decryptor = MegaDecrypt(full_key)
    decrypted_data = decryptor.decrypt(encrypted_data)
    mac_valid = decryptor.finalize()
    
    print(f"  - Datos desencriptados: {len(decrypted_data)} bytes")
    print(f"  - MAC válido: {mac_valid}")
    
    # Verificar que los datos coinciden
    if original_data == decrypted_data:
        print("✓ Test PASADO: Los datos originales y desencriptados son idénticos")
        return True
    else:
        print("✗ Test FALLIDO: Los datos no coinciden")
        # Mostrar diferencias
        diff_count = sum(1 for a, b in zip(original_data, decrypted_data) if a != b)
        print(f"  - Bytes diferentes: {diff_count} de {len(original_data)}")
        return False


if __name__ == "__main__":
    test_encrypt_decrypt_pipeline()
