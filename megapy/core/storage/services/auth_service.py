"""Authentication service."""
import binascii
from typing import Union, Dict, Any
from ..models import UserCredentials, SessionData, LoginResult
from ...api import APIClient
from ...crypto import Base64Encoder, PasswordKeyDeriverV2
from ...crypto.rsa import RSAService
from Crypto.Cipher import AES


class AuthService:
    """Handles authentication operations."""
    
    def __init__(self, api_client: APIClient, key_deriver=None, rsa_service=None):
        """Initializes authentication service."""
        self.api = api_client
        self.key_deriver = key_deriver or PasswordKeyDeriverV2()
        self.rsa_service = rsa_service or RSAService()
        self.encoder = Base64Encoder()
    
    def login(self, email: str, password: str) -> LoginResult:
        """Logs in with email and password."""
        credentials = UserCredentials(email.lower(), password)
        
        # Get user info
        user_data = self.api.request({'a': 'us0', 'user': credentials.email})
        
        # Derive password key
        password_key = self.key_deriver.derive(credentials.password, user_data['s'])
        
        # Calculate user hash
        aes = AES.new(password_key[:16], AES.MODE_ECB)
        user_hash = self.encoder.encode(password_key[16:])
        
        # Request login
        data = self.api.request({
            'a': 'us',
            'user': credentials.email,
            'uh': user_hash
        })
        
        # Decrypt master key
        encrypted_master_key = self.encoder.decode(data['k'])
        master_key = aes.decrypt(encrypted_master_key)
        
        # Decrypt private key and session ID
        aes = AES.new(master_key, AES.MODE_ECB)
        private_key = aes.decrypt(self.encoder.decode(data['privk']))
        
        sid_raw = self.rsa_service.decrypt(private_key, data['csid'])
        sid_hex = '0' + sid_raw if len(sid_raw) % 2 else sid_raw
        sid = self.encoder.encode(binascii.unhexlify(sid_hex)[:43])
        
        # Store session
        self.api.sid = sid
        
        # Get user info
        user_info = self.api.get_user_info()
        
        return LoginResult(
            session_id=sid,
            user_id=user_info.get('u', ''),
            user_name=user_info.get('name', ''),
            file_count=0,
            master_key=master_key
        )
    
    def resume(self, session: Union[str, SessionData, Dict[str, Any]]) -> Dict[str, Any]:
        """Resumes a previous session."""
        if isinstance(session, str):
            parts = session.split('|')
            if len(parts) != 2:
                raise ValueError("Invalid session format")
            self.api.sid = parts[0]
        elif isinstance(session, SessionData):
            self.api.sid = session.session_id
        else:
            self.api.sid = session.get('sid')
        
        user_data = self.api.get_user_info()
        return user_data

