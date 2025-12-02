import math
from Crypto.PublicKey import RSA
from Crypto.Util.number import bytes_to_long
from utils.logger import setup_logger

logger = setup_logger("RSA_helper", "DEBUG")

# Tamaño de limb (solo por consistencia, no lo usamos aquí)
bs = 28

def crypto_decode_priv_key_bytes(privk: bytes):
    """
    Toma un buffer MPI completo (2 bytes de longitud + payload) 
    que contiene p||q||d||u y devuelve una lista [mpi_p, mpi_q, mpi_d, mpi_u] (bytes).
    """
    logger.debug(f"crypto_decode_priv_key_bytes() called, total length={len(privk)}")
    data = privk
    segments = []
    for i in range(4):
        if len(data) < 2:
            logger.debug(f"  Segment {i}: datos insuficientes para leer encabezado MPI")
            return None
        # Leer longitud en bits
        b0, b1 = data[0], data[1]
        bits = (b0 << 8) | b1
        # Longitud en bytes = ceil(bits/8) + 2 de cabecera
        length = (bits + 7) // 8 + 2
        segment = data[:length]
        segments.append(segment)
        logger.debug(
            f"  Segment {i}: header bytes=0x{b0:02x},0x{b1:02x} -> bits={bits}, "
            f"length={length}, hex={segment.hex()[:64]}…"
        )
        data = data[length:]
    return segments

def mpi_to_int(data: bytes) -> int:
    """
    Convierte un bloque MPI (2 bytes de longitud + payload big-endian)
    a un entero Python, validando longitud.
    """
    b0, b1 = data[0], data[1]
    bits = (b0 << 8) | b1
    payload = data[2:]
    logger.debug(f"mpi_to_int(): bits={bits}, payload_len={len(payload)}")
    n = int.from_bytes(payload, byteorder="big")
    actual_bits = n.bit_length()
    logger.debug(f"  Converted to int={n} (bit_length={actual_bits})")
    if actual_bits != bits:
        logger.debug(f"  WARNING: header bits={bits} pero int.bit_length()={actual_bits}")
    return n

def build_rsa_from_mpis(mpi_p: bytes,
                        mpi_q: bytes,
                        mpi_d: bytes,
                        mpi_u: bytes) -> RSA.RsaKey:
    """
    Dado mpi_p, mpi_q, mpi_d, mpi_u (cada uno en formato MPI),
    construye y devuelve un objeto RsaKey de PyCryptodome listo para usar.
    """
    logger.debug("build_rsa_from_mpis() called")
    p = mpi_to_int(mpi_p)
    q = mpi_to_int(mpi_q)
    d = mpi_to_int(mpi_d)
    u = mpi_to_int(mpi_u)  # inverso de q mod p

    # Calcular n y e
    n = p * q
    phi = (p - 1) * (q - 1)
    e = pow(d, -1, phi)
    logger.debug(f"  p={p}, q={q}")
    logger.debug(f"  n=p*q={n}")
    logger.debug(f"  phi={phi}")
    logger.debug(f"  d={d}")
    logger.debug(f"  Computed public exponent e={e}")
    logger.debug(f"  u (q^(-1) mod p)={u}")

    # Construir la clave y devolverla
    key = RSA.construct((n, e, d, p, q, u))
    logger.debug("  RSA key constructed successfully")
    return key


def decode_privk(privk_bytes):
    parts = crypto_decode_priv_key_bytes(privk_bytes)
    if parts is None:
        raise ValueError("Clave MPI inválida o incompleta")

    mpi_p, mpi_q, mpi_d, mpi_u = parts

    # 3) Construir el RsaKey
    rsa_key = build_rsa_from_mpis(mpi_p, mpi_q, mpi_d, mpi_u)
    return rsa_key
    # 4) Descifrar algo
    from Crypto.Cipher import PKCS1_OAEP
    cipher = PKCS1_OAEP.new(rsa_key)
    with open("ciphertext.bin", "rb") as f:
        ciphertext = f.read()
    plaintext = cipher.decrypt(ciphertext)