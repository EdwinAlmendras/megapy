"""Event emitter implementation using Observer Pattern."""
from typing import Dict, List, Callable, Optional

class EventEmitter:
    """Event emitter using Observer Pattern."""
    
    def __init__(self, logger_name: str = "EVENT_EMITTER"):
        """Initializes event emitter."""
        self._events: Dict[str, List[Callable]] = {}
    
    def on(self, event: str, callback: Callable) -> 'EventEmitter':
        """Registers an event handler."""
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(callback)
        return self
    
    def emit(self, event: str, *args, **kwargs):
        """Emits an event."""
        if event in self._events:
            for callback in self._events[event]:
                callback(*args, **kwargs)
    
    def off(self, event: str, callback: Optional[Callable] = None) -> 'EventEmitter':
        """Removes an event handler."""
        if event not in self._events:
            return self
        
        if callback is None:
            del self._events[event]
        else:
            self._events[event] = [cb for cb in self._events[event] if cb != callback]
        
        return self

