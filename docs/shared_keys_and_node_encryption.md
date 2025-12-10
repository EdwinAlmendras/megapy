# Shared Keys and Node Encryption System

## Overview

This document explains how MEGA handles shared folders and the encryption system for nodes that are part of shared folders. The system involves multiple layers of encryption and key management.

## Share Keys (`ok` vs `ok0`)

MEGA API can return share keys in two formats:

### `ok` (Legacy/Cached Format)
- **Format**: Array of share objects
- **When used**: Legacy cached tree responses
- **Structure**: `[{"h": "handle", "ha": "auth_hash", "k": "encrypted_key"}, ...]`
- **Processing**: All shares processed at once

### `ok0` (Streaming Format)
- **Format**: Dictionary or array processed element by element
- **When used**: Streaming responses for better performance
- **Structure**: `{"handle": {"h": "handle", "ha": "auth_hash", "k": "encrypted_key"}, ...}` or array format
- **Processing**: Elements come one by one via `tree_ok0` handler
- **Priority**: If `ok0` exists, `ok` should be ignored (it's legacy cached data)

**Important**: The webclient processes `ok0` in streaming mode, while `ok` is for legacy/cached responses.

## Share Key Processing

### Authentication Hash Verification

Each share key entry contains:
- `h`: Share handler (folder handle)
- `ha`: Authentication hash (verifies share authenticity)
- `k`: Encrypted share key

The authentication hash is verified by:
1. Creating `auth = AES.encrypt_ECB(handler + handler)` using master key
2. Comparing `ha` with `auth` using constant-time comparison
3. If match, decrypting `k` with master key to get the share key

**Placeholder Data**: If `ha` or `k` are placeholder values (e.g., all 'A's like `"AAAAAAAAAAAAAAAAAAAAAA"`), they are skipped as they represent dummy/placeholder data.

### Example

```python
# API Response
{
    "ok": [
        {
            "h": "n0xg0ZRA",
            "ha": "encrypted_auth_hash",
            "k": "encrypted_share_key"
        }
    ]
}

# Processing
handler = "n0xg0ZRA"
auth = aes.encrypt_ecb(handler + handler)  # Verify authenticity
if auth == decoded_ha:
    share_key = aes.decrypt_ecb(decoded_k)  # Decrypt share key
    share_keys[handler] = share_key
```

## Node Key Encryption (`k` field)

### Single Key Format
```
"k": "userId:encryptedKey"
```
- Used for nodes owned by the current user
- Decrypted with master key

### Multiple Keys Format (Shared Nodes)
```
"k": "userId1:encryptedKey1/userId2:encryptedKey2"
```
- Used for nodes in shared folders
- Contains multiple `id:key` pairs separated by `/`
- Each pair represents the same node key encrypted with different keys

### Decryption Priority

When a node has multiple key pairs:

1. **Try user's own key first**: If `id` matches current user ID, decrypt with master key
2. **Try share keys**: If `id` is in `share_keys`, decrypt with that share key
3. **Skip if neither works**: Return `None` if no valid key found

### Example

```python
# Node in shared folder
node = {
    "h": "file_handle",
    "k": "-KkXosypUnM:fg7WqvVNM3_qvOx0DC1y6w/n0xg0ZRA:wxrXHL7LtYGX0vlTJCjRkg",
    "u": "-KkXosypUnM"  # Current user
}

# Processing
key_pairs = [
    "-KkXosypUnM:fg7WqvVNM3_qvOx0DC1y6w",  # User's key
    "n0xg0ZRA:wxrXHL7LtYGX0vlTJCjRkg"      # Share key
]

# Try user's key first
if id == user_id:
    key = decrypt_with_master_key(encrypted_key)
    
# If not found, try share key
elif id in share_keys:
    key = decrypt_with_share_key(encrypted_key, share_keys[id])
```

## Using Share Keys

### Getting Existing Share Key

When sharing a folder, check if it already has a share:

```python
folder = mega.get_node("folder_handle")
existing_shares = folder.shares  # Get share handles

if existing_shares and node_service:
    share_handle = existing_shares[0]
    if share_handle in node_service.share_keys:
        share_key = node_service.share_keys[share_handle]
        # Use existing share key instead of generating new one
```

### Creating Crypto Request

The `make_crypto_request` function uses share keys to encrypt node keys:

```python
# Automatically uses share keys from NodeService
crypto_request = folder.get_crypto_request(shares=[share_handle])

# Or manually
from megapy.core.crypto import make_crypto_request
crypto_request = make_crypto_request(
    share_keys=node_service.share_keys,
    sources=folder,  # Node object
    shares=[share_handle]
)
```

## Implementation Details

### KeyDecryptor

The `KeyDecryptor` class handles:
- Multiple `id:key` pairs in `k` field
- Priority-based decryption (user key → share key)
- Error handling for invalid keys

**Method**: `decrypt_node_key(node, master_key, share_keys=None)`

### NodeService

The `NodeService` class:
- Processes `ok` and `ok0` responses
- Stores share keys in `_share_keys` dictionary
- Provides `share_keys` property for access
- Verifies authentication hashes
- Skips placeholder data (all 'A's)

**Method**: `_process_share_keys(api_response)`

### Node Class

The `Node` class provides:
- `shares` property: Get share handles for node and parents
- `self_and_children` property: Get node and all descendants
- `get_crypto_request()` method: Generate crypto request automatically

## Best Practices

1. **Always check for existing shares** before creating new ones
2. **Use Node properties** (`shares`, `self_and_children`) instead of manual traversal
3. **Handle placeholder data** - skip entries with all 'A's or zeros
4. **Verify authentication hashes** to ensure share authenticity
5. **Use constant-time comparison** for security
6. **Process `ok0` before `ok`** - `ok0` takes priority in streaming mode

## Troubleshooting

### "Auth hash does not match"
- **Cause**: Share data may be placeholder (all 'A's)
- **Solution**: Check if `ha` or `k` are placeholder values and skip them
- **Also check**: Master key is correct, share data is from current session

### "No share keys found"
- **Cause**: Response doesn't have `ok` or `ok0` field
- **Solution**: Verify you're processing the correct API response
- **Check**: If shares exist in the account

### Share key not found when sharing
- **Cause**: Not checking for existing shares before generating new one
- **Solution**: Use `folder.shares` to check existing shares first
- **Check**: `node_service.share_keys` contains the share handle

### `ok0` vs `ok` confusion
- **Rule**: If `ok0` exists, process it and ignore `ok`
- **Reason**: `ok0` is streaming format, `ok` is legacy cached
- **Implementation**: Check for `ok0` first, fallback to `ok` only if `ok0` doesn't exist

## Code Flow

```
1. API Response → NodeService.load()
   ↓
2. _process_share_keys():
   - Check for ok0 (streaming) or ok (legacy)
   - Skip placeholder data (all 'A's)
   - Verify auth hash for each share
   - Decrypt and store share keys
   ↓
3. For each node in response.f:
   ↓
4. KeyDecryptor.decrypt_node_key():
   - If k has '/': split into pairs
   - Try decrypt with master_key (if id == user_id)
   - Try decrypt with share_keys (if id in share_keys)
   ↓
5. Return decrypted key
   ↓
6. Use key to decrypt attributes (name, etc.)
```

## References

- mega.js implementation: `mega/lib/storage.mjs` lines 152-167
- mega.js implementation: `mega/lib/mutable-file.mjs` lines 22-44
- mega.js implementation: `mega/lib/mutable-file.mjs` lines 753-786 (makeCryptoRequest)
- Webclient: `webclient/js/mega.js` line 2180 (tree_ok0)
- Webclient: `webclient/js/mega.js` line 3829 (ok vs ok0 handling)
