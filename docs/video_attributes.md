# MEGA Video/Media Attributes

This document explains how MEGA stores and handles video/audio metadata as file attributes.

## Overview

MEGA uses a special file attribute system to store media metadata (duration, resolution, codecs, etc.) for video and audio files. This metadata enables features like:

- Displaying video duration in the file browser
- Showing resolution information
- Determining if a file can be streamed
- Codec compatibility checking

## File Attribute Types

MEGA uses a `fa` (file attributes) field to store various types of metadata. For media files, two attribute types are used:

| Type | Name | Description |
|------|------|-------------|
| `0*` | Thumbnail | 240x240 JPEG thumbnail image |
| `1*` | Preview | Max 1024px JPEG preview image |
| `8*` | Media Attribute 8 | Core media info (resolution, duration, fps, format) |
| `9*` | Media Attribute 9 | Extended codec info (container, video codec, audio codec) |

### File Attribute String Format

The `fa` field contains attribute references in this format:

```
user_id:type*handle/user_id:type*handle/...
```

Example:
```
700:0*pz67EBzLoh4/700:1*KsGLS5rQ5jA/470:8*COXwfdF5an8/470:9*xyz123abc
```

This means:
- `700:0*pz67EBzLoh4` - Thumbnail (type 0) stored at handle `pz67EBzLoh4`
- `700:1*KsGLS5rQ5jA` - Preview (type 1) stored at handle `KsGLS5rQ5jA`
- `470:8*COXwfdF5an8` - Media attribute 8 with encrypted data
- `470:9*xyz123abc` - Media attribute 9 with codec info

---

## Media Attribute 8 (`:8*`)

This is the primary media attribute containing core video/audio information.

### Data Structure (8 bytes)

The attribute stores the following fields packed into 8 bytes (little-endian):

| Byte(s) | Bits | Field | Description |
|---------|------|-------|-------------|
| 0-1 | 15 bits | width | Video width in pixels |
| 1-2 | 15 bits | height | Video height in pixels |
| 3-4 | 8 bits | fps | Frames per second |
| 4-6 | 18 bits | playtime | Duration in seconds |
| 7 | 8 bits | shortformat | Format index (0-255) |

### Bit Packing Details

The values are compressed using a special encoding:

```python
# Width encoding (15 bits, max ~32000px)
width <<= 1
if width >= 32768:
    width = ((width - 32768) >> 3) | 1

# Height encoding (15 bits)  
height <<= 1
if height >= 32768:
    height = ((height - 32768) >> 3) | 1

# Playtime encoding (18 bits, supports very long durations)
playtime <<= 1
if playtime >= 262144:
    playtime = ((playtime - 262200) // 60) | 1

# FPS encoding (8 bits)
fps <<= 1
if fps >= 256:
    fps = ((fps - 256) >> 3) | 1
```

### Byte Layout

```
Byte 0: width[7:0] (low 8 bits, bit 0 is compression flag)
Byte 1: width[14:8] | (height[0] << 7)
Byte 2: height[8:1]
Byte 3: (height[14:9] & 0x3F) | ((fps & 3) << 6)
Byte 4: ((playtime & 3) << 6) | (fps >> 2)
Byte 5: playtime[9:2]
Byte 6: playtime[17:10]
Byte 7: shortformat
```

### Shortformat Values

The `shortformat` field indicates common format combinations:

| Value | Container | Video Codec | Audio Codec |
|-------|-----------|-------------|-------------|
| 0 | Custom (see attr 9) | Custom | Custom |
| 1 | mp42 | avc1 (H.264) | mp4a-40-2 (AAC) |
| 2 | mp42 | avc1 (H.264) | (none) |
| 3 | mp42 | (none) | mp4a-40-2 (AAC) |
| 255 | Unknown | Unknown | Unknown |

If `shortformat` is 0, the detailed codec information is stored in Media Attribute 9.

---

## Media Attribute 9 (`:9*`)

This attribute stores detailed codec information when `shortformat` is 0.

### Data Structure (8 bytes)

| Byte | Field | Description |
|------|-------|-------------|
| 0 | container | Container format ID |
| 1 | videocodec[7:0] | Video codec ID (low 8 bits) |
| 2 | videocodec[11:8] | audiocodec[3:0] | Mixed bits |
| 3 | audiocodec[11:4] | Audio codec ID (high 8 bits) |
| 4-7 | Reserved | Unused (zero) |

### Codec ID Mapping

MEGA maintains a codec list that maps IDs to codec names. This list is retrieved via the `mc` API command. Common mappings include:

**Containers:**
- mp42, mov, mkv, webm, avi, etc.

**Video Codecs:**
- avc1 (H.264), hevc (H.265), vp8, vp9, av1, etc.

**Audio Codecs:**
- mp4a-40-2 (AAC-LC), mp3, opus, vorbis, flac, etc.

---

## Encryption

Media attributes are encrypted using **XXTEA** (Corrected Block TEA) algorithm.

### Key Derivation

The encryption key is derived from the file's encryption key:

```python
def xxkey(file_key: List[int]) -> List[int]:
    """
    Extract XXTEA key from 8-element file key array.
    Uses elements 4-7 (last 4 uint32 values).
    """
    return [file_key[i + 4] for i in range(4)]
```

### Encryption Process

1. Pack media info into 8 bytes
2. Convert to 2 x uint32 array (little-endian)
3. Encrypt with XXTEA using derived key
4. Convert back to bytes
5. Encode as base64url

```python
def encode_media_attribute(info: MediaInfo, file_key: bytes) -> str:
    # Pack to 8 bytes
    data = pack_attr8(info)
    
    # Convert to uint32 array
    v = bytes_to_uint32_le(data)
    
    # Get XXTEA key from file key
    k = xxkey(file_key_to_array(file_key))
    
    # Encrypt
    encrypted = xxtea_encrypt(v, k)
    
    # Encode
    return "8*" + base64url_encode(uint32_to_bytes_le(encrypted))
```

### XXTEA Algorithm

```python
DELTA = 0x9E3779B9

def xxtea_encrypt(v: List[int], k: List[int]) -> List[int]:
    n = len(v) - 1
    z = v[n]
    sum_val = 0
    q = 6 + 52 // len(v)
    
    for _ in range(q):
        sum_val = (sum_val + DELTA) & 0xFFFFFFFF
        e = (sum_val >> 2) & 3
        
        for p in range(n):
            y = v[p + 1]
            v[p] = (v[p] + mx(sum_val, y, z, p, e, k)) & 0xFFFFFFFF
            z = v[p]
        
        y = v[0]
        v[n] = (v[n] + mx(sum_val, y, z, n, e, k)) & 0xFFFFFFFF
        z = v[n]
    
    return v

def mx(sum_val, y, z, p, e, k):
    return ((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((sum_val ^ y) + (k[p & 3 ^ e] ^ z))
```

---

## Uploading Media Attributes

Media attributes are uploaded using the `pfa` (put file attribute) API command.

### API Request

```json
{
    "a": "pfa",
    "n": "node_handle",
    "fa": "8*encoded_attr8/9*encoded_attr9"
}
```

### Response

On success, returns the updated `fa` string with server-assigned user IDs:

```
"470:8*COXwfdF5an8/470:9*xyz123abc"
```

---

## Implementation in MegaPy

### Extracting Media Info

```python
from megapy.core.attributes import MediaProcessor, MediaInfo

# Extract metadata from video file
processor = MediaProcessor()
info = processor.extract_metadata("video.mp4")

if info:
    print(f"Duration: {info.playtime} seconds")
    print(f"Resolution: {info.width}x{info.height}")
    print(f"FPS: {info.fps}")
    print(f"Format ID: {info.shortformat}")
```

### Encoding Media Attributes

```python
from megapy.core.attributes import MediaAttributeService, MediaInfo

service = MediaAttributeService()

# Create media info
info = MediaInfo(
    width=1920,
    height=1080,
    fps=30,
    playtime=120,  # 2 minutes
    shortformat=1   # MP4/H.264/AAC
)

# Encode to attribute string
file_key = b'\x00' * 32  # 32-byte file key
fa_string = service.encode(info, file_key)
# Returns: "8*COXwfdF5an8"
```

### Decoding Media Attributes

```python
from megapy.core.attributes import MediaAttributeService

service = MediaAttributeService()

# Decode from fa string
fa = "470:8*COXwfdF5an8"
file_key = node.key  # 32-byte key

info = service.decode(fa, file_key)
if info:
    print(f"Duration: {info.duration_formatted}")  # "2:00"
    print(f"Resolution: {info.resolution}")        # "1920x1080"
```

---

## Supported Formats

### Video Containers
- MP4, M4V, MOV (QuickTime)
- MKV (Matroska)
- WebM
- AVI
- FLV

### Video Codecs
- H.264 (AVC)
- H.265 (HEVC)
- VP8, VP9
- AV1

### Audio Codecs
- AAC (mp4a-40-2)
- MP3 (MPEG Audio)
- Opus
- Vorbis
- FLAC

---

## Critical Implementation Details: Endianness

### The Problem

During implementation, we encountered a critical bug where decoded media attributes showed completely wrong values:

| Field | Expected | Wrong Result |
|-------|----------|--------------|
| Duration | 4 seconds | 5,575,440 seconds |
| Resolution | 852x480 | 14000x6761 |
| FPS | 30 | 328 |
| Shortformat | 0 | 80 |

The values were astronomically wrong, indicating a fundamental issue with the encryption/decryption process.

### Root Cause: Mixed Endianness

The MEGA webclient uses **different byte orders** for different operations:

1. **File Key Conversion**: Uses **Big-Endian** (`base64_to_a32` function)
2. **Encrypted Data**: Uses **Little-Endian** for the 8-byte attribute data
3. **Decrypted Result**: Interpreted as **Little-Endian** bytes

The webclient's `base64_to_a32` function converts base64 to an array of 32-bit integers using **Big-Endian** byte order:

```javascript
// JavaScript webclient - base64_to_a32 uses Big-Endian
function base64_to_a32(s) {
    var a = [];
    s = base64urldecode(s);
    for (var i = 0; i < s.length; i += 4) {
        a.push(
            (s.charCodeAt(i) << 24) |      // Big-Endian: MSB first
            (s.charCodeAt(i + 1) << 16) |
            (s.charCodeAt(i + 2) << 8) |
            s.charCodeAt(i + 3)
        );
    }
    return a;
}
```

### The Solution

The file key must be converted to a uint32 array using **Big-Endian**, while the encrypted attribute data uses Little-Endian:

```python
def _key_to_array(file_key: bytes) -> List[int]:
    """
    Convert file key bytes to 8-element uint32 array.
    
    CRITICAL: Must use Big-Endian ('>8I') to match webclient's base64_to_a32.
    Using Little-Endian ('<8I') will produce completely wrong decryption results.
    """
    return list(struct.unpack('>8I', file_key[:32]))  # Big-Endian!

def _bytes_to_uint32_le(data: bytes) -> List[int]:
    """
    Convert encrypted attribute bytes to uint32 array.
    Uses Little-Endian for the attribute data itself.
    """
    return list(struct.unpack('<2I', data[:8]))  # Little-Endian
```

### Complete Decryption Flow

```python
def decode_media_attribute(fa: str, file_key: bytes) -> MediaInfo:
    # 1. Extract base64 encrypted data from fa string
    attr8_b64 = extract_attr8(fa)  # e.g., "bPgnl_qES_0"
    
    # 2. Decode base64 to bytes
    encrypted_bytes = base64_decode(attr8_b64)  # 8 bytes
    
    # 3. Convert encrypted bytes to uint32 array (Little-Endian)
    encrypted = struct.unpack('<2I', encrypted_bytes)
    
    # 4. Convert file key to uint32 array (BIG-ENDIAN - critical!)
    key_array = struct.unpack('>8I', file_key)
    
    # 5. Extract XXTEA key (elements 4-7)
    xxkey = [key_array[4], key_array[5], key_array[6], key_array[7]]
    
    # 6. Decrypt with XXTEA
    decrypted = xxtea_decrypt(list(encrypted), xxkey)
    
    # 7. Convert decrypted uint32 back to bytes (Little-Endian)
    decrypted_bytes = struct.pack('<2I', decrypted[0], decrypted[1])
    
    # 8. Parse the 8 bytes to extract width, height, fps, playtime, shortformat
    return parse_attr8(decrypted_bytes)
```

### Verification

After fixing the endianness, the same file now decodes correctly:

```
File: bAlkUCRD (908.9 KB) [852x480 0:04]
    Duration: 4s (0:04)        ✓ Correct!
    Resolution: 852x480        ✓ Correct!
    FPS: 30                    ✓ Correct!
    Shortformat: 0             ✓ Correct!
    Container: 129, Video: 887, Audio: 0
```

### Summary Table

| Operation | Byte Order | Python struct format |
|-----------|------------|---------------------|
| File key → uint32 array | **Big-Endian** | `'>8I'` |
| Encrypted attr → uint32 | Little-Endian | `'<2I'` |
| Decrypted uint32 → bytes | Little-Endian | `'<2I'` |

### Lesson Learned

When implementing crypto algorithms that interface with JavaScript code:
1. Carefully analyze how the webclient handles byte conversions
2. JavaScript's typed arrays (Uint32Array) use system endianness, but manual conversions often use Big-Endian
3. Test with real data from the production system to verify correctness
4. Small endianness errors can produce dramatically wrong results that look like random garbage

---

## References

- MEGA Webclient Source: `js/utils/media.js`, `js/crypto.js`
- XXTEA Algorithm: https://en.wikipedia.org/wiki/XXTEA
- MEGA API Documentation (unofficial)

---

## See Also

- [Thumbnail & Preview Generation](thumbnails.md)
- [File Encryption](encryption.md)
- [Upload Process](upload.md)
