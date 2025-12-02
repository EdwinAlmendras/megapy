"""RSA key decoder from MPI format."""
from Crypto.PublicKey import RSA
from utils.logger import setup_logger

logger = setup_logger("RSA_helper", "DEBUG")


class RSAKeyDecoder:
    """Decodes RSA private keys from MPI format."""
    
    @staticmethod
    def decode_priv_key_bytes(privk: bytes):
        """Decodes private key bytes into MPI segments."""
        logger.debug(f"crypto_decode_priv_key_bytes() called, total length={len(privk)}")
        data = privk
        segments = []
        for i in range(4):
            if len(data) < 2:
                logger.debug(f"  Segment {i}: datos insuficientes para leer encabezado MPI")
                return None
            b0, b1 = data[0], data[1]
            bits = (b0 << 8) | b1
            length = (bits + 7) // 8 + 2
            segment = data[:length]
            segments.append(segment)
            logger.debug(
                f"  Segment {i}: header bytes=0x{b0:02x},0x{b1:02x} -> bits={bits}, "
                f"length={length}, hex={segment.hex()[:64]}…"
            )
            data = data[length:]
        return segments
    
    @staticmethod
    def mpi_to_int(data: bytes) -> int:
        """Converts MPI block to integer."""
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
    
    @staticmethod
    def build_rsa_from_mpis(mpi_p: bytes, mpi_q: bytes, mpi_d: bytes, mpi_u: bytes) -> RSA.RsaKey:
        """Builds RSA key from MPI components."""
        logger.debug("build_rsa_from_mpis() called")
        p = RSAKeyDecoder.mpi_to_int(mpi_p)
        q = RSAKeyDecoder.mpi_to_int(mpi_q)
        d = RSAKeyDecoder.mpi_to_int(mpi_d)
        u = RSAKeyDecoder.mpi_to_int(mpi_u)
        
        n = p * q
        phi = (p - 1) * (q - 1)
        e = pow(d, -1, phi)
        logger.debug(f"  p={p}, q={q}")
        logger.debug(f"  n=p*q={n}")
        logger.debug(f"  phi={phi}")
        logger.debug(f"  d={d}")
        logger.debug(f"  Computed public exponent e={e}")
        logger.debug(f"  u (q^(-1) mod p)={u}")
        
        key = RSA.construct((n, e, d, p, q, u))
        logger.debug("  RSA key constructed successfully")
        return key
    
    def decode(self, privk_bytes: bytes) -> RSA.RsaKey:
        """Decodes private key from bytes to RSA key object."""
        parts = self.decode_priv_key_bytes(privk_bytes)
        if parts is None:
            raise ValueError("Clave MPI inválida o incompleta")
        
        mpi_p, mpi_q, mpi_d, mpi_u = parts
        return self.build_rsa_from_mpis(mpi_p, mpi_q, mpi_d, mpi_u)

