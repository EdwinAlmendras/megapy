"""
Async authentication service.

Handles MEGA authentication asynchronously.
"""
import binascii
from typing import Optional
from dataclasses import dataclass
from Crypto.Cipher import AES

from .async_client import AsyncAPIClient
from ..crypto import (
    Base64Encoder,
    PasswordKeyDeriverV2,
    RSAService
)


@dataclass
class AuthResult:
    """Authentication result."""
    session_id: str
    user_id: str
    user_name: str
    email: str
    master_key: bytes
    private_key: bytes

class AsyncAuthService:
    """
    Asynchronous authentication service.
    
    Handles login, session management, and key derivation.
    """
    
    def __init__(
        self,
        client: AsyncAPIClient,
        key_deriver: Optional[PasswordKeyDeriverV2] = None,
        rsa_service: Optional[RSAService] = None
    ):
        """
        Initialize auth service.
        
        Args:
            client: Async API client
            key_deriver: Password key deriver
            rsa_service: RSA service for decryption
        """
        self._client = client
        self._key_deriver = key_deriver or PasswordKeyDeriverV2()
        self._rsa_service = rsa_service or RSAService()
        self._encoder = Base64Encoder()
    
    async def login(self, email: str, password: str) -> AuthResult:
        """
        Login to MEGA.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            AuthResult with session info and master key
            
        Raises:
            MegaAPIError: If login fails
        """
        email = email.lower()
        
        # Step 1: Get user salt
        user_data = await self._client.request({
            'a': 'us0',
            'user': email
        })
        
        # Step 2: Derive password key
        password_key = self._key_deriver.derive(password, user_data['s'])
        
        # Step 3: Calculate user hash
        user_hash = self._encoder.encode(password_key[16:])
        
        # Step 4: Login request
        login_data = await self._client.request({
            'a': 'us',
            'user': email,
            'uh': user_hash
        })
        
        # Step 5: Decrypt master key
        encrypted_master_key = self._encoder.decode(login_data['k'])
        aes = AES.new(password_key[:16], AES.MODE_ECB)
        master_key = aes.decrypt(encrypted_master_key)
        
        # Step 6: Decrypt private key and session ID
        aes = AES.new(master_key, AES.MODE_ECB)
        private_key = aes.decrypt(self._encoder.decode(login_data['privk']))
        sid_raw = self._rsa_service.decrypt(private_key, login_data['csid'])
        sid_hex = '0' + sid_raw if len(sid_raw) % 2 else sid_raw
        session_id = self._encoder.encode(binascii.unhexlify(sid_hex)[:43])
        
        # Step 7: Set session ID on client
        self._client.session_id = session_id
        
        # Step 8: Get user info
        user_info = await self._client.get_user_info()
        
        return AuthResult(
            session_id=session_id,
            user_id=user_info.get('u', ''),
            user_name=user_info.get('name', ''),
            email=email,
            master_key=master_key,
            private_key=private_key
        )
    
    async def logout(self):
        """Logout from MEGA."""
        try:
            await self._client.request({'a': 'sml'})
        finally:
            self._client.session_id = None
