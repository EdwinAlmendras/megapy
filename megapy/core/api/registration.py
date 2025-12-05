"""
Account Registration - Minimalist OOP with Open/Closed Principle.

Single Responsibility: Handle account registration process.
Open/Closed: Base class closed for modification, open for extension via subclasses.
"""
import os
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from Crypto.Cipher import AES

from .async_client import AsyncAPIClient
from ..crypto import Base64Encoder, PasswordKeyDeriverV2

logger = logging.getLogger(__name__)


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


@dataclass
class RegistrationResult:
    """Registration result."""
    success: bool
    user_handle: Optional[str] = None
    requires_email_confirmation: bool = True
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
    async def register(self, data: RegistrationData) -> RegistrationResult:
        """
        Register a new account.
        
        Args:
            data: Registration data
            
        Returns:
            RegistrationResult
        """
        pass
    
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
        
        Based on mega-api: deriveKeys function.
        
        Args:
            password: User password
            master_key: Master encryption key
            client_random_value: 16 random bytes (CRV)
            
        Returns:
            Dictionary with crv, k (encrypted master key), hak (hashed auth key)
        """
        # Create salt from CRV
        salt = self._create_salt(client_random_value)
        
        # Derive password key using PBKDF2
        derived_key = self._key_deriver.derive(password, salt)
        password_key = derived_key[:16]  # First 16 bytes
        user_hash = derived_key[16:]     # Last 16 bytes
        
        # Encrypt master key with password key
        aes = AES.new(password_key, AES.MODE_ECB)
        encrypted_master_key = aes.encrypt(master_key)
        
        # Create hashed authentication key (HAK)
        hak = hashlib.sha256(user_hash).digest()[:16]
        
        return {
            'crv': client_random_value,
            'k': encrypted_master_key,
            'hak': hak
        }


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
    
    async def register(self, data: RegistrationData) -> RegistrationResult:
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
    
    async def register(self, data: RegistrationData) -> RegistrationResult:
        """
        Register a standard account.
        
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
            
            # Step 2: Generate client random value
            client_random_value = os.urandom(16)
            
            # Step 3: Derive keys from password
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


class BusinessAccountRegistration(StandardAccountRegistration):
    """
    Business account registration (extends standard).
    
    Open/Closed: Extends StandardAccountRegistration without modifying it.
    """
    
    async def register(self, data: RegistrationData) -> RegistrationResult:
        """
        Register a business account.
        
        Extends standard registration with business-specific parameters.
        """
        # For now, same as standard but can be extended
        result = await super().register(data)
        
        # Future: Add business-specific logic here
        # e.g., set business flags, create business structure, etc.
        
        return result

