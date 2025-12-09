import hashlib
import base64
from typing import Tuple


def solve_hashcash(x_hashcash_header: str) -> str:
    """
    Procesa el header X-Hashcash y genera la solución del proof-of-work.
    
    Args:
        x_hashcash_header: Header en formato "1:easiness:token:nonce"
    
    Returns:
        Nuevo header en formato "1:nonce:solution"
    
    Raises:
        ValueError: Si el header es inválido
    """
    # Parsear el header
    parts = x_hashcash_header.split(':')
    
    if len(parts) != 4:
        raise ValueError(f"Header inválido: se esperan 4 partes, se obtuvieron {len(parts)}")
    
    x = int(parts[0])
    easiness = int(parts[1])
    token_b64 = parts[2]
    nonce = parts[3]
    
    # Validar
    if x != 1:
        raise ValueError(f"Versión inválida: se esperaba 1, se obtuvo {x}")
    if not (0 <= easiness < 256):
        raise ValueError(f"Easiness fuera de rango: {easiness}")
    
    # Generar la solución
    solution = gencash(token_b64, easiness)
    
    # Retornar el nuevo header
    return f"1:{nonce}:{solution}"


def gencash(token: str, easiness: int) -> str:
    """
    Genera la solución del proof-of-work tipo hashcash.
    
    Args:
        token: Token en base64
        easiness: Nivel de dificultad (0-255)
    
    Returns:
        Solución en base64
    """
    # Calcular el threshold
    threshold = (((easiness & 63) << 1) + 1) << ((easiness >> 6) * 7 + 3)
    
    # Decodificar el token
    from megapy.core.crypto import Base64
    token_bytes = Base64.decode(token)
    
    # Crear buffer: 4 bytes para prefijo + token repetido 262144 veces
    buffer_size = 4 + len(token_bytes) * 262144
    buffer = bytearray(buffer_size)
    
    # Llenar el buffer con el token repetido
    for i in range(262144):
        offset = 4 + i * len(token_bytes)
        buffer[offset:offset + len(token_bytes)] = token_bytes
    
    # Buscar un prefijo válido
    prefix = bytearray(4)
    
    while True:
        # Incrementar el prefijo (como un contador little-endian)
        for j in range(4):
            prefix[j] = (prefix[j] + 1) & 0xFF
            if prefix[j] != 0:
                break
        
        # Actualizar el buffer con el nuevo prefijo
        buffer[0:4] = prefix
        
        # Calcular SHA-256
        hash_result = hashlib.sha256(buffer).digest()
        
        # Extraer los primeros 4 bytes como uint32 big-endian
        hash_value = int.from_bytes(hash_result[0:4], byteorder='big')
        
        # Verificar si cumple con el threshold
        if hash_value <= threshold:
            # Retornar el prefijo en base64
            return base64.b64encode(prefix).decode('ascii')


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo de header recibido en respuesta 402
    header_input = "1:192:1765313612:5YCt3A9UTyl-71NZ4H0FiV8YCUlt7LB_Xiu8GfQ0z23v_C3pPjOtxl90pSDj3hzq"
    
    try:
        result = solve_hashcash(header_input)
        print(f"Header resuelto: {result}")
    except ValueError as e:
        print(f"Error: {e}")