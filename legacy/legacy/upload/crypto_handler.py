from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Util.strxor import strxor
from Crypto.Util._raw_api import load_pycryptodome_raw_lib, create_string_buffer, get_raw_buffer, c_size_t
from typing import Tuple, Optional, List, Dict, Set
from utils.logger import setup_logger
import struct
import asyncio
import concurrent.futures
import threading
import os
import time
import ctypes
from Crypto.Util.number import long_to_bytes
import numpy as np
import queue
import logging
logger = setup_logger("FileCrypto", logging.INFO)

# Cargar librerías C para operaciones vectorizadas
_raw_cbc_lib = load_pycryptodome_raw_lib("Crypto.Cipher._raw_cbc",
    """
    int CBC_update(void *state, const uint8_t *in, uint8_t *out, size_t in_len);
    """)

# Tamaño del bloque AES en bytes
AES_BLOCK_SIZE = 16

# ======= OPTIMIZADOR DE BAJO NIVEL =======
# Esta función C procesa miles de bloques XOR a máxima velocidad
def fast_xor_and_cipher(cipher, data, initial_value):
    """
    Función ultra-optimizada para calcular CBC-MAC.
    Usa strxor de C nativo para las operaciones XOR.
    
    Args:
        cipher: Cifrador AES en modo ECB
        data: Datos a procesar
        initial_value: Valor inicial para XOR
        
    Returns:
        Resultado del CBC-MAC
    """
    # Verificar que tenemos al menos 16 bytes
    if not data:
        return bytes(initial_value)
    
    # Convertir a arreglo de bytes
    mac = bytearray(initial_value)
    
    # Procesar todos los bloques completos
    full_blocks_len = len(data) - (len(data) % 16)
    for i in range(0, full_blocks_len, 16):
        block = data[i:i+16]
        # XOR usando strxor en C - mucho más rápido que Python
        xored = strxor(bytes(mac), block)
        # Cifrar
        mac = bytearray(cipher.encrypt(xored))
    
    # Procesar el último bloque si es incompleto
    remaining = len(data) % 16
    if remaining > 0:
        last_block = data[full_blocks_len:] + b'\0' * (16 - remaining)
        # XOR usando strxor en C
        xored = strxor(bytes(mac), last_block)
        # Cifrar
        mac = bytearray(cipher.encrypt(xored))
    
    return bytes(mac)

def merge_key_mac(key: bytes, mac: bytes) -> bytes:
    """Combina la clave de cifrado y el MAC en el formato que MEGA espera"""
    return key + mac

class MegaEncrypt:
    """
    Cifrador MEGA con procesamiento asíncrono para evitar bloquear el event loop.
    """
    
    # Thread pool dedicado únicamente a cálculos de MAC
    _mac_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    
    def __init__(self, key: Optional[bytes] = None, total_chunks: int = 0):
        """
        Inicializa cifrador con clave.
        
        Args:
            key: Clave de 24 bytes (16 bytes AES + 8 bytes nonce)
            total_chunks: Número esperado de chunks (opcional)
        """
        # Inicialización de clave
        self.key = key or os.urandom(24)
        self.aes_key = self.key[:16]
        self.nonce = self.key[16:24]
        
        # Cifrador CTR optimizado para datos (operación rápida)
        ctr = Counter.new(
            64,
            prefix=self.nonce,
            initial_value=0,
            little_endian=False
        )
        self.cipher = AES.new(self.aes_key, AES.MODE_CTR, counter=ctr)
        
        # Cifrador ECB para MAC (sin estado, thread-safe)
        self.mac_cipher = AES.new(self.aes_key, AES.MODE_ECB)
        
        # Valor MAC inicial según MEGA: h := (n << 64) + n
        n = int.from_bytes(self.nonce, byteorder='big')
        h = (n << 64) | n
        self.mac_template = h.to_bytes(16, byteorder='big')
        
        # Protección para cifrado secuencial
        self.last_index = -1
        self.cipher_lock = threading.Lock()
        
        # Cola para procesamiento MAC en background
        self.mac_queue = queue.Queue()
        self.mac_process_thread = None
        self.mac_accumulator = bytearray(16)  # Inicializado con ceros
        self.mac_lock = threading.Lock()
        self.processing_complete = threading.Event()  # Señal para finalización
        
        # Iniciar thread de procesamiento
        self._start_mac_processing_thread()

    def _start_mac_processing_thread(self):
        """Inicia thread dedicado a procesar MACs de forma continua"""
        def process_mac_queue():
            processed_count = 0
            total_process_time = 0
            total_size_processed = 0
            
            while True:
                try:
                    # Esperar datos o señal de finalización
                    item = self.mac_queue.get(timeout=0.1)
                    
                    # Si recibimos None, es señal para terminar
                    if item is None:
                        self.mac_queue.task_done()
                        # Mostrar estadísticas de procesamiento
                        if processed_count > 0:
                            avg_time = total_process_time / processed_count
                            mbps = (total_size_processed * 8) / (total_process_time * 1_000_000) if total_process_time > 0 else 0
                            logger.debug(f"Estadísticas MAC: {processed_count} chunks procesados, " +
                                       f"tiempo total: {total_process_time:.2f}s, " +
                                       f"promedio: {avg_time:.4f}s/chunk, " +
                                       f"velocidad: {mbps:.2f} Mbps")
                        break
                        
                    # Procesar MAC para este chunk
                    data = item
                    data_size = len(data)
                    
                    # Medir tiempo de procesamiento
                    start_time = time.time()
                    
                    chunk_mac = self._calculate_chunk_mac(data)
                    
                    # Actualizar MAC acumulativo
                    with self.mac_lock:
                        xored = strxor(self.mac_accumulator, chunk_mac)
                        self.mac_accumulator = bytearray(self.mac_cipher.encrypt(xored))
                    
                    # Calcular tiempo y actualizar estadísticas
                    process_time = time.time() - start_time
                    processed_count += 1
                    total_process_time += process_time
                    total_size_processed += data_size
                    
                    # Log cada 10 chunks o si el procesamiento tarda más de 0.1s
                    if processed_count % 10 == 0 or process_time > 0.1:
                        mbps = (data_size * 8) / (process_time * 1_000_000) if process_time > 0 else 0
                        queue_size = self.mac_queue.qsize()
                        logger.debug(f"MAC procesado #{processed_count}: {data_size/1024:.1f}KB en {process_time:.4f}s " +
                                   f"({mbps:.2f} Mbps), cola: {queue_size} pendientes")
                    
                    # Marcar como completado
                    self.mac_queue.task_done()
                    
                except queue.Empty:
                    # Simplemente continuar esperando
                    continue
                except Exception as e:
                    logger.error(f"Error procesando MAC: {e}")
                    self.mac_queue.task_done()
            
            # Señalar que hemos terminado todo el procesamiento
            self.processing_complete.set()
            logger.debug(f"Thread de procesamiento MAC finalizado")
        
        # Iniciar thread dedicado
        self.mac_process_thread = threading.Thread(
            target=process_mac_queue,
            daemon=True
        )
        self.mac_process_thread.start()
        logger.debug("Thread de procesamiento MAC iniciado")

    def encrypt(self, chunk_index: int, data: bytes) -> bytes:
        """
        Cifra un chunk - NO BLOQUEANTE.
        
        Args:
            chunk_index: Índice del chunk
            data: Datos a cifrar
            
        Returns:
            Datos cifrados
        """
        start_time = time.time()
        
        # Verificación de orden (CTR debe ser secuencial)
        if chunk_index != self.last_index + 1:
            logger.warning(f"Chunk {chunk_index} fuera de orden! Esperado {self.last_index + 1}")
        self.last_index = chunk_index
        
        # OPERACIÓN RÁPIDA: Cifrado CTR sincronizado (no bloquea el event loop)
        with self.cipher_lock:
            encrypted = self.cipher.encrypt(data)
        
        cipher_time = time.time() - start_time
        
        # OPERACIÓN LENTA: Poner en cola para cálculo de MAC en background
        self.mac_queue.put(bytes(data))  # Copy para thread safety
        
        total_time = time.time() - start_time
        
        # Log para chunks grandes o si el cifrado tarda más de lo esperado
        if len(data) > 1024*1024 or total_time > 0.01:
            mbps = (len(data) * 8) / (cipher_time * 1_000_000) if cipher_time > 0 else 0
            logger.debug(f"Chunk {chunk_index} cifrado: {len(data)/1024/1024:.2f}MB en {cipher_time:.4f}s " +
                       f"({mbps:.2f} Mbps), cola MAC: {self.mac_queue.qsize()}")
        
        return encrypted
    
    def _calculate_chunk_mac(self, data: bytes) -> bytes:
        """
        Calcula CBC-MAC para un chunk usando código C nativo.
        """
        start_time = time.time()
        
        # Usar la función optimizada con código C
        mac = fast_xor_and_cipher(self.mac_cipher, data, self.mac_template)
        
        process_time = time.time() - start_time
        mbps = (len(data) * 8) / (process_time * 1_000_000) if process_time > 0 else 0
        
        # Solo mostrar log si es un chunk grande o el procesamiento es lento
        if len(data) > 1024*1024 or process_time > 0.1:
            logger.debug(f"Cálculo MAC interno (optimizado C): {len(data)/1024/1024:.2f}MB en {process_time:.4f}s " +
                       f"({mbps:.2f} Mbps)")
        
        return bytes(mac)

    def finalize(self, timeout=1.0) -> bytes:
        """
        Finaliza cifrado y genera clave.

        Args:
            timeout: Tiempo máximo a esperar en segundos (None = esperar todo)
            
        Returns:
            Clave final en formato MEGA
        """
        start_time = time.time()
        queue_size = self.mac_queue.qsize()
        logger.debug(f"Iniciando finalize(), {queue_size} MACs pendientes en cola")
        
        # 1. Señalizar al thread de procesamiento que termine después
        #    de procesar todos los chunks pendientes
        self.mac_queue.put(None)
        
        # 2. Esperar a que se complete el procesamiento (con timeout opcional)
        wait_start = time.time()
        completed = self.processing_complete.wait(timeout=timeout)
        wait_time = time.time() - wait_start
        
        if completed:
            logger.debug(f"Procesamiento MAC completado en {wait_time:.2f}s")
        elif timeout is not None:
            logger.warning(f"finalize() alcanzó timeout de {timeout}s, usando MAC parcial, " +
                         f"quedan ~{self.mac_queue.qsize()} MACs en cola")
        
        # 3. Calcular meta-MAC con lo que tenemos hasta ahora
        meta_time_start = time.time()
        meta_mac = self._calculate_metamac()
        
        # 4. Crear formato final MEGA
        key = self._create_key_format(meta_mac)
        
        total_time = time.time() - start_time
        logger.debug(f"finalize() completado en {total_time:.2f}s " +
                   f"(espera: {wait_time:.2f}s, meta+formato: {time.time() - meta_time_start:.4f}s)")
        
        return key
    
    def _calculate_metamac(self) -> bytes:
        """Calcula meta-MAC final según especificación MEGA"""
        # Thread-safe: copia para evitar que cambie mientras calculamos
        with self.mac_lock:
            mac_data = bytes(self.mac_accumulator)
            
        # Extraer valores de 32 bits
        parts = struct.unpack(">IIII", mac_data)
        
        # Calcular meta-MAC: (a^b)|(c^d)
        meta_mac_high = parts[0] ^ parts[1]
        meta_mac_low = parts[2] ^ parts[3]
        
        # Empaquetar como 8 bytes
        return struct.pack(">II", meta_mac_high, meta_mac_low)
    
    def _create_key_format(self, meta_mac: bytes) -> bytes:
        """Crea formato final de clave MEGA"""
        # Desempaquetar componentes
        key_parts = struct.unpack(">IIII", self.aes_key)
        nonce_parts = struct.unpack(">II", self.nonce)
        meta_parts = struct.unpack(">II", meta_mac)
        
        # Empaquetar formato final
        return struct.pack(">IIIIIIII",
            key_parts[0] ^ nonce_parts[0],
            key_parts[1] ^ nonce_parts[1], 
            key_parts[2] ^ meta_parts[0],
            key_parts[3] ^ meta_parts[1],
            nonce_parts[0],
            nonce_parts[1],
            meta_parts[0], 
            meta_parts[1]
        )

# Mantener compatibilidad
def create_mega_key_format(aes_key, nonce, meta_mac):
    """Función legacy para crear formato de clave MEGA"""
    key_parts = struct.unpack(">IIII", aes_key)
    nonce_parts = struct.unpack(">II", nonce)
    meta_parts = struct.unpack(">II", meta_mac)
    
    return struct.pack(">IIIIIIII",
        key_parts[0] ^ nonce_parts[0],
        key_parts[1] ^ nonce_parts[1],
        key_parts[2] ^ meta_parts[0],
        key_parts[3] ^ meta_parts[1],
        nonce_parts[0],
        nonce_parts[1],
        meta_parts[0],
        meta_parts[1]
    )