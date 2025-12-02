# Upload Performance Analysis

## Problem

megapy uploads are slow compared to mega_api.

## Root Cause: Synchronous MAC Calculation

### megapy (SLOW) - Blocking MAC:
```python
def encrypt_chunk(self, chunk_index: int, data: bytes) -> bytes:
    encrypted = self._cipher.encrypt(data)  # Fast ~1ms
    
    # BLOCKING - calculates MAC synchronously
    chunk_mac = self._calculate_chunk_mac(data)  # SLOW ~50-100ms per MB
    with self._mac_lock:
        xored = strxor(bytes(self._mac_accumulator), chunk_mac)
        self._mac_accumulator = bytearray(self._mac_cipher.encrypt(xored))
    
    return encrypted  # Returns AFTER MAC is done
```

### mega_api (FAST) - Background MAC:
```python
def encrypt(self, chunk_index: int, data: bytes) -> bytes:
    encrypted = self.cipher.encrypt(data)  # Fast ~1ms
    
    # NON-BLOCKING - queue for background processing
    self.mac_queue.put(bytes(data))  # Instant
    
    return encrypted  # Returns IMMEDIATELY
```

## How MEGA Upload Works

1. **AES-CTR Encryption**: Must be sequential (counter mode)
2. **CBC-MAC Calculation**: Can be done in parallel/background
3. **Upload**: Can happen while MAC is calculating

### Timeline Comparison:

**megapy (sequential):**
```
[Encrypt1][MAC1][Upload1][Encrypt2][MAC2][Upload2]...
           ^^^^          BOTTLENECK
```

**mega_api (parallel MAC):**
```
[Encrypt1][Upload1][Encrypt2][Upload2]...
     └──[MAC1]──────[MAC2]──────────────┘ (background thread)
```

## CBC-MAC Algorithm (for reference)

```
MAC = AES_ECB(template)  // template = nonce || nonce

For each 16-byte block in data:
    MAC = AES_ECB(MAC XOR block)

Return MAC
```

This is O(n) where n = file_size / 16. For a 14MB file = ~900,000 AES operations!

## Solution

Move MAC calculation to background thread:

1. Create a dedicated MAC processing thread
2. Queue chunks for MAC calculation after encryption
3. Continue with upload while MAC processes
4. Wait for MAC completion only at finalize()

## Key Components

### Thread Pool for MAC
```python
self._mac_thread = threading.Thread(target=self._process_mac_queue)
self._mac_queue = queue.Queue()
```

### Non-blocking encrypt
```python
def encrypt_chunk(self, data):
    encrypted = self._cipher.encrypt(data)
    self._mac_queue.put(data)  # Don't wait
    return encrypted
```

### Blocking finalize
```python
def finalize(self):
    self._mac_queue.put(None)  # Signal end
    self._processing_complete.wait()  # Wait for all MACs
    return self._create_key(self._meta_mac)
```
