"""
Account Registration - Minimalist OOP with Open/Closed Principle.

Single Responsibility: Handle account registration process.
Open/Closed: Base class closed for modification, open for extension via subclasses.
"""
import os
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Util.number import long_to_bytes

from .async_client import AsyncAPIClient
from ..crypto import Base64Encoder, PasswordKeyDeriverV2, AESCrypto
from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class RegistrationData:
    """Registration data container."""
    email: str
    first_name: str
    last_name: str
    password: str
    master_key: Optional[bytes] = None
    user_handle: Optional[str] = None
    session_id: Optional[str] = None
    client_random_value: Optional[bytes] = None


@dataclass
class RegistrationResult:
    """Registration result."""
    success: bool
    user_handle: Optional[str] = None
    requires_email_confirmation: bool = True
    message: Optional[str] = None


@dataclass
class ConfirmCodeResult:
    """Email confirmation result."""
    success: bool
    email: Optional[str] = None
    name: Optional[str] = None
    user_handle: Optional[str] = None
    message: Optional[str] = None


@dataclass
class FinalizeResult:
    """Registration finalization result."""
    success: bool
    message: Optional[str] = None


class AccountRegistrationBase(ABC):
    """
    Base class for account registration.
    
    Open/Closed Principle: Closed for modification, open for extension.
    Subclasses can extend behavior without modifying this base class.
    """
    
    def __init__(self, api_client: AsyncAPIClient):
        """
        Initialize registration handler.
        
        Args:
            api_client: AsyncAPIClient instance
        """
        self._api = api_client
        self._encoder = Base64Encoder()
        self._key_deriver = PasswordKeyDeriverV2()
    
    @abstractmethod
    async def init_register(self, data: RegistrationData) -> RegistrationResult:
        """
        Initialize account registration (step 1).
        
        Args:
            data: Registration data
            
        Returns:
            RegistrationResult
        """
        pass
    
    # Keep register as alias for backward compatibility
    async def register(self, data: RegistrationData) -> RegistrationResult:
        """Alias for init_register for backward compatibility."""
        return await self.init_register(data)
    
    def _create_salt(self, client_random_value: bytes) -> bytes:
        """
        Create salt from client random value.
        
        Based on mega-api: createSalt function.
        
        Args:
            client_random_value: 16 random bytes
            
        Returns:
            32-byte salt
        """
        mega = b"mega.nz"
        max_length = 200
        padding = b"P" * (max_length - len(mega))
        mega_padded = mega + padding
        
        combined = mega_padded + client_random_value
        return hashlib.sha256(combined).digest()
    
    def _derive_keys_from_password(
        self,
        password: str,
        master_key: bytes,
        client_random_value: bytes
    ) -> Dict[str, bytes]:
        """
        Derive keys from password for registration.
        
        Based on webclient: deriveKeysFromPassword function.
        Matches webclient's process exactly:
        1. Trim password and convert to UTF-8 bytes
        2. Create salt from CRV
        3. Derive 32-byte key using PBKDF2 (100k iterations, SHA-512)
        4. Split: first 16 bytes = encryption key, last 16 bytes = auth key
        5. Encrypt master key with encryption key (AES-ECB)
        6. Hash auth key with SHA-256 and take first 16 bytes (HAK)
        
        Args:
            password: User password (will be trimmed)
            master_key: Master encryption key (16 bytes)
            client_random_value: 16 random bytes (CRV)
            
        Returns:
            Dictionary with crv, k (encrypted master key), hak (hashed auth key)
        """
        # Validate master key size (must be exactly 16 bytes)
        if len(master_key) != 16:
            raise ValueError(f"Master key must be exactly 16 bytes, got {len(master_key)}")
        
        # Validate client random value size (must be exactly 16 bytes)
        if len(client_random_value) != 16:
            raise ValueError(f"Client random value must be exactly 16 bytes, got {len(client_random_value)}")
        
        # Trim password (like webclient: $.trim(password))
        password_trimmed = password.strip()
        
        # Create salt from CRV (matches webclient's createSalt)
        salt = self._create_salt(client_random_value)
        
        # Derive password key using PBKDF2 (matches webclient: 100k iterations, 32 bytes)
        # Password is converted to UTF-8 bytes by PasswordKeyDeriverV2
        derived_key = self._key_deriver.derive(password_trimmed, salt)
        
        # Split derived key: first 16 bytes = encryption key, last 16 bytes = auth key
        password_key = derived_key[:16]  # Derived Encryption Key
        user_hash = derived_key[16:32]   # Derived Authentication Key
        
        # Encrypt master key with password key using AES-ECB (matches webclient)
        # Use AESCrypto from crypto module
        aes_crypto = AESCrypto(password_key)
        encrypted_master_key = aes_crypto.encrypt_ecb(master_key)
        
        # Create hashed authentication key (HAK)
        # SHA-256 of auth key, then take first 16 bytes (matches webclient)
        hak = hashlib.sha256(user_hash).digest()[:16]
        
        return {
            'crv': client_random_value,
            'k': encrypted_master_key,
            'hak': hak
        }
    
    def _int_to_mpi(self, value: int) -> bytes:
        """
        Convert integer to MPI (Multi-Precision Integer) format.
        
        MPI format: 2 bytes (bit length) + big-endian bytes
        
        Args:
            value: Integer to convert
            
        Returns:
            MPI-formatted bytes
        """
        if value == 0:
            return b'\x00\x00'
        
        # Convert to bytes (big-endian)
        value_bytes = long_to_bytes(value)
        bit_length = value.bit_length()
        
        # MPI header: 2 bytes for bit length
        header = bytes([
            (bit_length >> 8) & 0xFF,
            bit_length & 0xFF
        ])
        
        return header + value_bytes
    
    def _generate_rsa_keypair(self) -> Tuple[RSA.RsaKey, bytes, bytes]:
        """
        Generate RSA key pair and encode in MEGA format.
        
        Returns:
            Tuple of (RSA key object, encoded private key bytes, encoded public key bytes)
        """
        # Generate 2048-bit RSA key pair
        key = RSA.generate(2048)
        
        # Extract components
        p = key.p
        q = key.q
        d = key.d
        n = key.n
        e = key.e
        
        # Calculate u = q^(-1) mod p (CRT coefficient)
        u = pow(q, -1, p)
        
        # Encode private key: q, p, d, u (in that order)
        privk_q = self._int_to_mpi(q)
        privk_p = self._int_to_mpi(p)
        privk_d = self._int_to_mpi(d)
        privk_u = self._int_to_mpi(u)
        
        privk_encoded = privk_q + privk_p + privk_d + privk_u
        
        # Pad to multiple of 16 bytes
        padding_needed = (16 - (len(privk_encoded) % 16)) % 16
        if padding_needed > 0:
            privk_encoded += os.urandom(padding_needed)
        
        # Encode public key: n, e
        pubk_n = self._int_to_mpi(n)
        pubk_e = self._int_to_mpi(e)
        pubk_encoded = pubk_n + pubk_e
        
        return key, privk_encoded, pubk_encoded


class EphemeralAccountCreator(AccountRegistrationBase):
    """
    Creates ephemeral (anonymous) accounts.
    
    Single Responsibility: Create anonymous accounts only.
    """
    
    async def create_ephemeral_account(self) -> RegistrationData:
        """
        Create an ephemeral (anonymous) account.
        
        Based on mega-api anonymous() method.
        
        Returns:
            RegistrationData with master_key and user_handle set
            
        Raises:
            RuntimeError: If account creation fails
        """
        # Generate random keys
        master_key = os.urandom(16)
        password_key = os.urandom(16)
        ssc = os.urandom(16)  # Session self challenge
        
        # Encrypt master key with password key
        aes = AES.new(password_key, AES.MODE_ECB)
        encrypted_master_key = aes.encrypt(master_key)
        
        # Create timestamp (ssc + encrypted ssc)
        aes_master = AES.new(master_key, AES.MODE_ECB)
        encrypted_ssc = aes_master.encrypt(ssc)
        ts = ssc + encrypted_ssc
        
        # Request to create anonymous account
        try:
            response = await self._api.request({
                'a': 'up',
                'k': self._encoder.encode(encrypted_master_key),
                'ts': self._encoder.encode(ts)
            })
            
            # Response is the user handle (string) or dict with result
            user_handle = response if isinstance(response, str) else response.get('result')
            if not user_handle or (isinstance(user_handle, int) and user_handle < 0):
                error_code = user_handle if isinstance(user_handle, int) else -1
                raise RuntimeError(f"Failed to create ephemeral account: error {error_code}")
            
            # Get session
            session_response = await self._api.request({
                'a': 'us',
                'user': user_handle
            })
            
            # Decrypt master key from response
            k_encrypted = session_response.get('k')
            if not k_encrypted:
                raise RuntimeError("No master key in session response")
            
            k_encrypted_bytes = self._encoder.decode(k_encrypted)
            master_key = aes.decrypt(k_encrypted_bytes)
            
            tsid = session_response.get('tsid')
            if tsid:
                self._api.session_id = tsid
            
            # Create result
            data = RegistrationData(
                email="",
                first_name="",
                last_name="",
                password="",
                master_key=master_key,
                user_handle=user_handle,
                session_id=tsid
            )
            
            logger.info(f"Ephemeral account created: {user_handle}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to create ephemeral account: {e}")
            raise RuntimeError(f"Ephemeral account creation failed: {e}") from e
    
    async def init_register(self, data: RegistrationData) -> RegistrationResult:
        """Not used for ephemeral accounts."""
        raise NotImplementedError("Use create_ephemeral_account() instead")


class StandardAccountRegistration(AccountRegistrationBase):
    """
    Standard account registration with email confirmation.
    
    Single Responsibility: Handle standard user registration.
    """
    
    def __init__(self, api_client: AsyncAPIClient):
        """Initialize standard registration."""
        super().__init__(api_client)
        self._ephemeral_creator = EphemeralAccountCreator(api_client)
    
    async def init_register(self, data: RegistrationData) -> RegistrationResult:
        """
        Initialize standard account registration (step 1).
        
        Process:
        1. Create ephemeral account
        2. Derive keys from password
        3. Send registration request (uc2)
        4. Send user profile info (up)
        
        Args:
            data: Registration data with email, names, password
            
        Returns:
            RegistrationResult
        """
        try:
            # Step 1: Create ephemeral account
            ephemeral = await self._ephemeral_creator.create_ephemeral_account()
            data.master_key = ephemeral.master_key
            data.user_handle = ephemeral.user_handle
            data.session_id = ephemeral.session_id
            
            # Step 2: Generate client random value
            client_random_value = os.urandom(16)
            # Store in data for later use
            data.client_random_value = client_random_value
            
            # Step 3: Derive keys from password
            if not data.master_key:
                raise RuntimeError("Master key not set after ephemeral account creation")
            
            derived = self._derive_keys_from_password(
                data.password,
                data.master_key,
                client_random_value
            )
            
            # Step 4: Send registration request (uc2)
            full_name = f"{data.first_name} {data.last_name}"
            
            uc2_response = await self._api.request({
                'a': 'uc2',
                'v': 2,  # Version 2 protocol
                'm': self._encoder.encode(data.email.lower().encode('utf-8')),  # Email
                'n': self._encoder.encode(full_name.encode('utf-8')),  # Full name
                'crv': self._encoder.encode(derived['crv']),  # Client Random Value
                'k': self._encoder.encode(derived['k']),  # Encrypted Master Key
                'hak': self._encoder.encode(derived['hak'])  # Hashed Auth Key
            })
            
            # Check response - uc2 returns 0 on success, error code otherwise
            result_code = uc2_response if isinstance(uc2_response, int) else uc2_response.get('result', 0)
            if result_code != 0:
                return RegistrationResult(
                    success=False,
                    message=f"Registration failed with error: {result_code}"
                )
            
            # Step 5: Send user profile information
            await self._api.request({
                'a': 'up',
                'terms': 'Mq',  # Terms accepted
                'firstname': self._encoder.encode(data.first_name.encode('utf-8')),
                'lastname': self._encoder.encode(data.last_name.encode('utf-8')),
                'name2': self._encoder.encode(full_name.encode('utf-8'))
            })
            
            logger.info(f"Account registration initiated for {data.email}")
            
            return RegistrationResult(
                success=True,
                user_handle=data.user_handle,
                requires_email_confirmation=True,
                message="Registration successful. Please check your email for confirmation."
            )
            
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return RegistrationResult(
                success=False,
                message=f"Registration failed: {str(e)}"
            )
    
    async def confirm_code(self, confirm_code: str) -> ConfirmCodeResult:
        """
        Confirm email with confirmation code (step 2).
        
        Based on webclient security.verifyEmailConfirmCode().
        
        Args:
            confirm_code: Confirmation code from email (base64url encoded)
            
        Returns:
            ConfirmCodeResult with email, name, and user handle
        """
        try:
            # Send ud2 request to confirm the code
            response = await self._api.request({
                'a': 'ud2',
                'c': confirm_code
            })
            
            logger.debug(f"ud2 response type: {type(response)}, value: {response}")
            
            # Response format can be:
            # 1. dict with 'result' key containing [email, name, user_handle]
            # 2. dict with 'result' key containing array where result[1] = [email, name, user_handle]
            # 3. Direct array [email, name, user_handle]
            
            result_data = None
            
            if isinstance(response, dict):
                if 'result' in response:
                    result_data = response['result']
                    # Check if result is nested array (result[1] contains the data)
                    if isinstance(result_data, list) and len(result_data) > 1:
                        if isinstance(result_data[1], list) and len(result_data[1]) >= 3:
                            result_data = result_data[1]
                else:
                    # Try to find array in response values
                    for value in response.values():
                        if isinstance(value, list) and len(value) >= 3:
                            result_data = value
                            break
            elif isinstance(response, list):
                # Direct array response
                if len(response) > 1 and isinstance(response[1], list) and len(response[1]) >= 3:
                    result_data = response[1]
                elif len(response) >= 3:
                    result_data = response
            
            if result_data and isinstance(result_data, list) and len(result_data) >= 3:
                email_encoded = result_data[0]
                name_encoded = result_data[1]
                user_handle = result_data[2]
                
                # Decode email and name
                email = self._encoder.decode(email_encoded).decode('utf-8')
                name = self._encoder.decode(name_encoded).decode('utf-8')
                
                logger.info(f"Email confirmed: {email}")
                
                return ConfirmCodeResult(
                    success=True,
                    email=email,
                    name=name,
                    user_handle=user_handle,
                    message="Email confirmed successfully"
                )
            
            logger.warning(f"Unexpected response format: {response}")
            return ConfirmCodeResult(
                success=False,
                message=f"Invalid confirmation code or response format: {response}"
            )
            
        except Exception as e:
            logger.error(f"Email confirmation failed: {e}", exc_info=True)
            return ConfirmCodeResult(
                success=False,
                message=f"Email confirmation failed: {str(e)}"
            )
    
    async def finalize_registration(
        self,
        password: str,
        confirm_code: str,
        master_key: bytes,
        client_random_value: bytes
    ) -> FinalizeResult:
        """
        Finalize registration by completing verification and generating RSA keys (step 3).
        
        Process:
        1. Send erx request with r='v2' to complete email verification
        2. Generate RSA key pair
        3. Encrypt private key with master key
        4. Send up request with privk and pubk
        
        Based on webclient security.completeVerifyEmail() and key generation.
        
        Args:
            password: User password
            confirm_code: Confirmation code from email
            master_key: Master encryption key (from init_register)
            client_random_value: Client random value (from init_register)
            
        Returns:
            FinalizeResult
        """
        try:
            # Step 1: Derive keys from password (same as in init_register)
            derived = self._derive_keys_from_password(
                password,
                master_key,
                client_random_value
            )
            
            """ # Step 2: Send erx request to complete verification
            # Note: x = encrypted master key, y = hashed auth key (matching webclient)
            erx_response = await self._api.request({
                'a': 'erx',
                'c': confirm_code,
                'r': 'v2',  # Version 2 protocol
                'z': self._encoder.encode(derived['crv']),  # Client Random Value
                'x': self._encoder.encode(derived['k']),    # Encrypted Master Key
                'y': self._encoder.encode(derived['hak'])   # Hashed Auth Key
            })
            
            # Check if erx was successful
            if isinstance(erx_response, int) and erx_response != 0:
                return FinalizeResult(
                    success=False,
                    message=f"Verification completion failed with error: {erx_response}"
                ) """
            
            # Step 3: Generate RSA key pair
            rsa_key, privk_encoded, pubk_encoded = self._generate_rsa_keypair()
            
            # Step 4: Encrypt private key with master key
            aes = AES.new(master_key, AES.MODE_ECB)
            
            # Pad private key to multiple of 16 bytes if needed
            privk_padded = privk_encoded
            if len(privk_padded) % 16 != 0:
                padding = 16 - (len(privk_padded) % 16)
                privk_padded += b'\x00' * padding
            
            # Encrypt private key
            privk_encrypted = aes.encrypt(privk_padded)
            
            # Step 5: Send up request with RSA keys
            up_response = await self._api.request({
                'a': 'up',
                'privk': self._encoder.encode(privk_encrypted),
                'pubk': self._encoder.encode(pubk_encoded)
            })
            
            # Check response
            if isinstance(up_response, int) and up_response != 0:
                return FinalizeResult(
                    success=False,
                    message=f"Failed to upload RSA keys: {up_response}"
                )
            
            logger.info("Registration finalized successfully with RSA keys")
            
            return FinalizeResult(
                success=True,
                message="Registration completed successfully. Account is now fully activated."
            )
            
        except Exception as e:
            logger.error(f"Registration finalization failed: {e}")
            return FinalizeResult(
                success=False,
                message=f"Registration finalization failed: {str(e)}"
            )


class BusinessAccountRegistration(StandardAccountRegistration):
    """
    Business account registration (extends standard).
    
    Open/Closed: Extends StandardAccountRegistration without modifying it.
    """
    
    async def init_register(self, data: RegistrationData) -> RegistrationResult:
        """
        Register a business account.
        
        Extends standard registration with business-specific parameters.
        """
        # For now, same as standard but can be extended
        result = await super().init_register(data)
        
        # Future: Add business-specific logic here
        # e.g., set business flags, create business structure, etc.
        
        return result

