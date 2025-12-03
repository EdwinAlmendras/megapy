# File Modification Time (mtime)

This document explains how MEGA stores and handles file modification timestamps, and how megapy implements this feature to match the official MEGA web client behavior.

## Overview

When uploading files to MEGA, the original file's modification time (mtime) can be preserved. This is stored as a Unix timestamp in the encrypted file attributes, allowing MEGA to display when the file was last modified on the user's local system, rather than just when it was uploaded.

## How MEGA Stores Modification Time

### Attribute Storage

The modification time is stored in the **`t` attribute** within the encrypted file attributes JSON. This is the same structure used for other file metadata like the filename (`n`), labels (`lbl`), and favorites (`fav`).

```json
{
  "n": "document.pdf",
  "t": 1701532800,
  "lbl": 1
}
```

The `t` value is a **Unix timestamp** (seconds since epoch, January 1, 1970 UTC).

### How the Web Client Works

Based on analysis of MEGA's official webclient source code:

1. **On Upload**: The webclient reads `file.lastModified` (JavaScript's File API) and divides by 1000 to get seconds:
   ```javascript
   var ts = (file.lastModifiedDate || file.lastModified || 0) / 1000;
   ```

2. **Attribute Encryption**: The mtime is included in the attributes object before encryption:
   ```javascript
   // In crypto_makeattr()
   if (n.mtime) {
       ar.t = n.mtime;
   }
   ```

3. **On Download/Display**: The webclient decrypts attributes and reads the `t` field:
   ```javascript
   // In crypto_procattr()
   if (typeof o.t === 'number') {
       n.mtime = o.t;
   }
   ```

### Alternative Storage: File Hash

MEGA also supports embedding the modification time in the file's fingerprint hash. The hash format includes:
- CRC32 checksum of file content
- Serialized modification timestamp

This is used primarily for duplicate detection and file verification.

## Implementation in megapy

### FileAttributes Model

The `FileAttributes` class includes an `mtime` field:

```python
from megapy.core.upload.models import FileAttributes
from datetime import datetime

# Using Unix timestamp (int)
attrs = FileAttributes(
    name="document.pdf",
    mtime=1701532800
)

# Using datetime object (auto-converted to timestamp)
attrs = FileAttributes(
    name="document.pdf",
    mtime=datetime(2023, 12, 2, 12, 0, 0)
)

# Serializes to: {'n': 'document.pdf', 't': 1701532800}
print(attrs.to_dict())
```

### Automatic mtime Detection

When uploading files, megapy automatically reads the file's modification time from the filesystem if not explicitly provided:

```python
async with MegaClient("email", "password") as mega:
    # mtime is automatically set from the file's st_mtime
    node = await mega.upload("document.pdf")
```

The coordinator reads the file's mtime using Python's `pathlib`:

```python
file_mtime = int(path.stat().st_mtime)
```

### Manual mtime Override

You can explicitly set the modification time:

```python
from megapy.core.upload.models import FileAttributes, UploadConfig
from datetime import datetime

# Set a specific modification time
attrs = FileAttributes(
    name="old_document.pdf",
    mtime=datetime(2020, 1, 15, 10, 30, 0)
)

config = UploadConfig(
    file_path="document.pdf",
    target_folder_id=folder_id,
    attributes=attrs
)

node = await mega.upload_with_config(config)
```

## Reading mtime from Downloaded Nodes

When listing or downloading files, the mtime is available in the node attributes:

```python
async with MegaClient("email", "password") as mega:
    root = await mega.get_root()
    
    for node in root:
        if node.attributes and hasattr(node.attributes, 'mtime'):
            mtime = node.attributes.mtime
            if mtime:
                from datetime import datetime
                dt = datetime.fromtimestamp(mtime)
                print(f"{node.name}: modified {dt}")
```

## Technical Notes

### Timestamp Format
- **Type**: Integer (Unix timestamp)
- **Unit**: Seconds since epoch (1970-01-01 00:00:00 UTC)
- **Precision**: Second-level precision
- **Range**: Standard 32-bit or 64-bit Unix timestamp range

### Encryption
The mtime is stored in the encrypted attributes block, meaning:
- It's encrypted with the file's AES key
- It cannot be read without the decryption key
- It's protected by MEGA's end-to-end encryption

### Compatibility
This implementation matches the official MEGA web client behavior, ensuring:
- Files uploaded with megapy show correct modification times in MEGA apps
- Files downloaded from MEGA preserve their original modification times

## Example: Full Upload with mtime

```python
import asyncio
from megapy import MegaClient
from megapy.core.upload.models import FileAttributes
from datetime import datetime

async def upload_with_mtime():
    async with MegaClient("user@example.com", "password") as mega:
        # Automatic mtime (from file system)
        node1 = await mega.upload("recent_file.pdf")
        print(f"Uploaded with auto mtime: {node1.name}")
        
        # Custom mtime (e.g., for archived files)
        attrs = FileAttributes(
            name="archived_report.pdf",
            mtime=datetime(2019, 6, 15, 14, 30, 0),
            label=2  # Orange label
        )
        
        # Note: Using the upload method with custom attributes
        node2 = await mega.upload(
            "report.pdf",
            name="archived_report.pdf"
        )
        print(f"Uploaded with custom mtime: {node2.name}")

asyncio.run(upload_with_mtime())
```

## References

- MEGA webclient source: `js/transfers/utils.js` (fingerprint with mtime)
- MEGA webclient source: `nodedec.js` (crypto_makeattr, crypto_procattr)
- MEGA API documentation: File attributes specification
