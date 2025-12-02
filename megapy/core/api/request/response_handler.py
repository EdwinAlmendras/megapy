"""Response handler for API responses."""
import json
from typing import Dict, Any, Optional, Callable
from ..errors import MegaAPIError


class ResponseHandler:
    """Handles API responses."""
    
    @staticmethod
    def parse_response(response) -> Any:
        """Parses JSON response."""
        try:
            return response.json()
        except ValueError:
            raise Exception("Empty or invalid response")
    
    @staticmethod
    def normalize_response(resp_data: Any) -> Any:
        """Normalizes response data."""
        if isinstance(resp_data, list) and len(resp_data) > 0:
            return resp_data[0]
        return resp_data
    
    @staticmethod
    def handle_error(resp_data: Any) -> Optional[MegaAPIError]:
        """Handles error responses."""
        if isinstance(resp_data, int) and resp_data < 0:
            return MegaAPIError(resp_data)
        return None
    
    @staticmethod
    def process_response(resp_data: Any, callback: Optional[Callable] = None) -> Any:
        """Processes response with optional callback."""
        normalized = ResponseHandler.normalize_response(resp_data)
        error = ResponseHandler.handle_error(normalized)
        
        if callback:
            callback(error, normalized if not error else None)
            return None
        elif error:
            raise error
        
        return normalized

