"""Node repository using Repository Pattern."""
from typing import Dict, List, Optional, Any
from ...api import APIClient


class NodeRepository:
    """Repository for node data access."""
    
    def __init__(self, api_client: APIClient):
        """Initializes node repository."""
        self.api = api_client
    
    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Gets all nodes from API."""
        response = self.api.get_files()
        if not response or 'f' not in response:
            return []
        return response.get('f', [])
    
    def get_node(self, handle: str) -> Optional[Dict[str, Any]]:
        """Gets a specific node by handle."""
        nodes = self.get_all_nodes()
        for node in nodes:
            if node.get('h') == handle:
                return node
        return None
    
    def get_shared_keys(self) -> Dict[str, bytes]:
        """Extracts shared keys from filesystem response."""
        response = self.api.get_files()
        if not response or 'ok' not in response:
            return {}
        
        shared_keys = {}
        for share_data in response.get('ok', []):
            if 'h' in share_data and 'k' in share_data:
                shared_keys[share_data['h']] = share_data['k']
        
        return shared_keys

