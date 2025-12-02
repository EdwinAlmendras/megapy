"""MEGA API error codes and exceptions."""
from typing import Dict


class APIErrorCodes:
    """MEGA API error codes."""
    
    ERROR_CODES: Dict[int, str] = {
        1: 'EINTERNAL (-1): An internal error has occurred. Please submit a bug report, detailing the exact circumstances in which this error occurred.',
        2: 'EARGS (-2): You have passed invalid arguments to this command.',
        3: 'EAGAIN (-3): A temporary congestion or server malfunction prevented your request from being processed. No data was altered.',
        4: 'ERATELIMIT (-4): You have exceeded your command weight per time quota. Please wait a few seconds, then try again.',
        5: 'EFAILED (-5): The upload failed. Please restart it from scratch.',
        6: 'ETOOMANY (-6): Too many concurrent IP addresses are accessing this upload target URL.',
        7: 'ERANGE (-7): The upload file packet is out of range or not starting and ending on a chunk boundary.',
        8: 'EEXPIRED (-8): The upload target URL you are trying to access has expired. Please request a fresh one.',
        9: 'ENOENT (-9): Object (typically, node or user) not found. Wrong password?',
        10: 'ECIRCULAR (-10): Circular linkage attempted',
        11: 'EACCESS (-11): Access violation (e.g., trying to write to a read-only share)',
        12: 'EEXIST (-12): Trying to create an object that already exists',
        13: 'EINCOMPLETE (-13): Trying to access an incomplete resource',
        14: 'EKEY (-14): A decryption operation failed',
        15: 'ESID (-15): Invalid or expired user session, please relogin',
        16: 'EBLOCKED (-16): User blocked',
        17: 'EOVERQUOTA (-17): Request over quota',
        18: 'ETEMPUNAVAIL (-18): Resource temporarily not available, please try again later',
        19: 'ETOOMANYCONNECTIONS (-19)',
        24: 'EGOINGOVERQUOTA (-24)',
        25: 'EROLLEDBACK (-25)',
        26: 'EMFAREQUIRED (-26): Multi-Factor Authentication Required',
        27: 'EMASTERONLY (-27)',
        28: 'EBUSINESSPASTDUE (-28)',
        29: 'EPAYWALL (-29): ODQ paywall state',
        400: 'ETOOERR (-400)',
        401: 'ESHAREROVERQUOTA (-401)'
    }
    
    @classmethod
    def get_message(cls, code: int) -> str:
        """Gets error message for error code."""
        return cls.ERROR_CODES.get(abs(code), f"Unknown error: {code}")


class MegaAPIError(Exception):
    """Exception raised for MEGA API errors."""
    
    def __init__(self, code: int):
        self.code = code
        self.message = APIErrorCodes.get_message(code)
        super().__init__(self.message)

