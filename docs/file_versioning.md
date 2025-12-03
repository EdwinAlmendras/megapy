# File Versioning

This document explains how MEGA handles file versioning and how megapy implements the `update()` method to create new versions of existing files.

## Overview

MEGA supports file versioning, which means when you update a file, the old version is preserved and accessible through the version history. This is useful for:

- Tracking changes to documents over time
- Recovering previous versions if needed
- Maintaining a history of modifications

## How MEGA Versioning Works

### The `ov` Parameter

When creating a new node (file) via the MEGA API, you can include an `ov` (old version) parameter that points to an existing file handle. When MEGA receives this:

1. The new file is created with the new content
2. The old file becomes a "previous version" of the new file
3. Both files share the same parent folder
4. The version chain is maintained by MEGA

### API Request Structure

```json
{
  "a": "p",
  "t": "parent_folder_handle",
  "n": [{
    "h": "upload_token",
    "t": 0,
    "a": "encrypted_attributes",
    "k": "encrypted_key",
    "ov": "existing_file_handle"
  }]
}
```

The key difference from a normal upload is the `ov` field which tells MEGA to treat this as a version update.

### Version Chain Structure

MEGA organizes versions in a parent-child chain:

```
Current Version (visible in file manager)
    └── Previous Version 1
        └── Previous Version 2
            └── Previous Version 3 (oldest)
```

Each file node can have one child that represents its previous version.

## Implementation in megapy

### The `update()` Method

megapy provides a simple `update()` method that handles all the complexity:

```python
async def update(
    self,
    file: Union[str, MegaFile],      # File to update
    new_content: Union[str, Path],    # Path to new content
    name: Optional[str] = None,       # Optional new name
    progress_callback: Optional[Callable] = None,
    auto_thumb: bool = True,
    thumbnail: Optional[bytes] = None,
    preview: Optional[bytes] = None
) -> MegaFile
```

### Basic Usage

```python
import asyncio
from megapy import MegaClient

async def main():
    async with MegaClient("email@example.com", "password") as mega:
        # Upload initial version
        file_v1 = await mega.upload("report_v1.pdf", name="report.pdf")
        print(f"Uploaded v1: {file_v1.handle}")
        
        # Update with new content (creates version 2)
        file_v2 = await mega.update(file_v1, "report_v2.pdf")
        print(f"Updated to v2: {file_v2.handle}")
        
        # Update again (creates version 3)
        file_v3 = await mega.update(file_v2, "report_v3.pdf")
        print(f"Updated to v3: {file_v3.handle}")

asyncio.run(main())
```

### Update by Path

You can also reference the file by its MEGA path:

```python
async with MegaClient("session") as mega:
    # Update file by path
    new_version = await mega.update(
        "/Documents/report.pdf",
        "local_updated_report.pdf"
    )
```

### Update with New Name

```python
async with MegaClient("session") as mega:
    # Update and rename in one operation
    new_version = await mega.update(
        old_file,
        "quarterly_data.csv",
        name="Q4_2024_data.csv"
    )
```

### Update with Progress Tracking

```python
from megapy import UploadProgress

def on_progress(p: UploadProgress):
    pct = p.percentage
    print(f"\rUpdating: {pct:.1f}%", end="")

async with MegaClient("session") as mega:
    new_version = await mega.update(
        "/Documents/large_file.zip",
        "large_file_updated.zip",
        progress_callback=on_progress
    )
    print(f"\nUpdate complete!")
```

### Update Media Files

For images and videos, thumbnails and previews are automatically generated:

```python
async with MegaClient("session") as mega:
    # Thumbnails auto-generated for the new version
    new_version = await mega.update(
        "/Photos/vacation.jpg",
        "vacation_edited.jpg"
    )
    
    # Or provide custom thumbnail
    new_version = await mega.update(
        "/Videos/project.mp4",
        "project_final.mp4",
        thumbnail="custom_thumb.jpg"
    )
```

## Low-Level Usage with UploadConfig

For more control, you can use `UploadConfig` directly:

```python
from megapy.core.upload import UploadCoordinator, UploadConfig
from megapy.core.upload.models import FileAttributes

async with MegaClient("session") as mega:
    # Get the file to replace
    existing_file = await mega.get("/Documents/data.csv")
    
    # Create config with replace_handle
    config = UploadConfig(
        file_path="new_data.csv",
        target_folder_id=existing_file.parent_handle,
        attributes=FileAttributes(name="data.csv"),
        replace_handle=existing_file.handle  # This creates the version
    )
    
    coordinator = UploadCoordinator(
        api_client=mega._api,
        master_key=mega._master_key
    )
    
    result = await coordinator.upload(config)
    print(f"New version handle: {result.node_handle}")
```

## Version History Access

In the MEGA web client, you can access version history by:

1. Right-clicking on a file
2. Selecting "Version history"
3. Viewing all previous versions with timestamps

Each version shows:
- File name
- Size
- Modification date
- Who made the change

From the version history, you can:
- Download any version
- Revert to a previous version
- Delete specific versions

## Technical Details

### How Versions are Stored

MEGA stores versions using a parent-child relationship in the node tree:

```
File Node (current version)
├── h: "ABC123" (handle)
├── p: "folder_handle" (parent folder)
├── t: 0 (file type)
├── a: {...} (encrypted attributes)
└── Children:
    └── Previous Version Node
        ├── h: "XYZ789"
        ├── p: "ABC123" (parent is current version!)
        └── ...
```

The key insight is that previous versions have their parent (`p`) set to the current version's handle, not the folder.

### Version Count

MEGA tracks the number of versions in the `tvf` (total version files) attribute of the current version node.

### Encryption

Each version has its own encryption key. When you update a file:

1. A new random key is generated for the new version
2. The old version keeps its original key
3. Both versions are independently decryptable

This means you need the appropriate key to access each version.

## Best Practices

1. **Use meaningful names**: When renaming during update, use clear version indicators
2. **Track important versions**: Consider adding custom attributes to mark significant versions
3. **Clean up old versions**: MEGA's storage quota includes all versions
4. **Handle errors gracefully**: The update operation can fail if the original file was deleted

## Error Handling

```python
try:
    new_version = await mega.update(file, "new_content.txt")
except FileNotFoundError as e:
    print(f"Original file or new content not found: {e}")
except ValueError as e:
    print(f"Cannot update (maybe it's a folder?): {e}")
except Exception as e:
    print(f"Update failed: {e}")
```

## Comparison with Other Operations

| Operation | Creates Version | Preserves Old | Same Handle |
|-----------|-----------------|---------------|-------------|
| `upload()` | No | No | N/A (new file) |
| `update()` | Yes | Yes | No (new handle) |
| `rename()` | No | No | Yes |
| `move()` | No | No | Yes |

## References

- MEGA webclient source: `js/fm/fileversioning.js`
- MEGA webclient source: `js/transfers/upload2.js` (see `_replaces` and `ov`)
- MEGA API: `p` command with `ov` parameter
