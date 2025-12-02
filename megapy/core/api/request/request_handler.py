"""Request handler using Template Method pattern."""
import json
from typing import Dict, Optional, Callable, Any
from .request_builder import RequestBuilder
from .response_handler import ResponseHandler
from ..retry import RetryStrategy, ExponentialBackoffStrategy
from ..errors import MegaAPIError
from utils.logger import setup_logger


class RequestHandler:
    """Handles API requests using Template Method pattern."""
    
    def __init__(self, session, retry_strategy: RetryStrategy = None):
        """Initializes request handler."""
        self.session = session
        self.retry_strategy = retry_strategy or ExponentialBackoffStrategy()
        self.logger = setup_logger("REQUEST_HANDLER")
    
    def execute(self, builder: RequestBuilder, json_data: Dict, 
                callback: Optional[Callable] = None, retry_count: int = 0, 
                max_retries: int = 4) -> Any:
        """Executes request with retry logic."""
        builder.update_from_data(json_data)
        url = builder.build_url(json_data.pop('_querystring', None))
        headers = builder.build_headers(json_data.pop('_hashcash', None))
        data = builder.build_data(json_data)
        
        try:
            response = self.session.post(url, headers=headers, data=data)
            
            if 'X-Hashcash' in response.headers:
                from ...crypto import generate_hashcash_token
                hashcash_challenge = response.headers['X-Hashcash']
                json_data['_hashcash'] = generate_hashcash_token(hashcash_challenge)
                return self.execute(builder, json_data, callback, retry_count, max_retries)
            
            resp_data = ResponseHandler.parse_response(response)
            normalized = ResponseHandler.normalize_response(resp_data)
            error = ResponseHandler.handle_error(normalized)
            
            if error and self.retry_strategy.should_retry(error.code, retry_count, max_retries):
                self.retry_strategy.wait(retry_count)
                return self.execute(builder, json_data, callback, retry_count + 1, max_retries)
            
            return ResponseHandler.process_response(normalized, callback)
            
        except Exception as e:
            if callback:
                callback(e)
                return None
            raise

