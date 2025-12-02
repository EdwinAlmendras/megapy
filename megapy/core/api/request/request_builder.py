"""Request builder for API requests."""
import json
from urllib.parse import urlencode
from typing import Dict, Optional


class RequestBuilder:
    """Builds API requests."""
    
    def __init__(self, gateway: str, counter_id: str, session_id: Optional[str] = None):
        """Initializes request builder."""
        self.gateway = gateway
        self.counter_id = counter_id
        self.session_id = session_id
    
    def build_url(self, params: Optional[Dict] = None) -> str:
        """Builds request URL."""
        base_params = {'id': self.counter_id}
        if self.session_id:
            base_params['sid'] = self.session_id
        if params:
            base_params.update(params)
        return f"{self.gateway}cs?{urlencode(base_params)}"
    
    def update_from_data(self, json_data: Dict):
        """Updates builder from request data."""
        if '_querystring' in json_data:
            # Handle querystring params if needed
            pass
    
    def build_headers(self, hashcash: Optional[str] = None) -> Dict[str, str]:
        """Builds request headers."""
        headers = {'Content-Type': 'application/json'}
        if hashcash:
            headers['X-Hashcash'] = hashcash
        return headers
    
    def build_data(self, json_data: Dict) -> str:
        """Builds request data."""
        return json.dumps([json_data])

