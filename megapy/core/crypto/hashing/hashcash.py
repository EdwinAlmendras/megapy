"""Hashcash token generation."""
import hashlib


class HashcashGenerator:
    """Generates hashcash tokens for proof-of-work."""
    
    @staticmethod
    def generate(challenge: str) -> str:
        """Generates a hashcash token for the given challenge."""
        nonce = 0
        target = challenge.split(':')[0]
        
        while True:
            token = f"{target}:{nonce}"
            digest = hashlib.sha256(token.encode()).hexdigest()
            
            if digest.startswith("0" * len(target)):
                return token
            
            nonce += 1

