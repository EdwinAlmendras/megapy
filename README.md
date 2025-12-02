# MegaPy

A professional, async-first Python library for MEGA cloud storage. Built with SOLID principles and modern design patterns.

## Features

- **Async/Await**: Fully asynchronous API using aiohttp
- **Session Persistence**: SQLite-based sessions like Telethon
- **Tree Navigation**: Professional file system interface with path-based navigation
- **Custom Attributes**: Extended metadata support with minimized keys
- **Thumbnail/Preview**: Auto-generation for images and videos
- **Configurable**: Proxy, SSL, timeouts, retries, custom headers
- **Secure**: Full support for MEGA's end-to-end encryption
- **SOLID**: Clean architecture with dependency injection
- **Tested**: 340+ unit tests with real account e2e tests

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

```
pycryptodome    # Cryptographic operations
aiohttp         # Async HTTP client
cryptography    # Advanced crypto primitives
Pillow          # Image processing (optional, for thumbnails)
```

---

## Quick Start

```python
import asyncio
from megapy import MegaClient

async def main():
    async with MegaClient("email@example.com", "password") as mega:
        # Tree navigation
        root = await mega.get_root()
        print(await mega.tree())
        
        # Upload with custom attributes
        node = await mega.upload("document.pdf")
        
        # Navigate
        docs = root / "Documents"
        for file in docs:
            print(file)

asyncio.run(main())
```

---

# API Reference

## MegaClient

The main high-level client for MEGA operations.

### Constructor

```python
MegaClient(
    email_or_session: str,           # Email or session name
    password: Optional[str] = None,  # Password (None for session mode)
    config: Optional[APIConfig] = None,
    session_storage: Optional[SessionStorage] = None
)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_logged_in` | `bool` | True if authenticated |
| `session_file` | `Optional[Path]` | Path to session file |

### Methods

#### Authentication

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `start()` | `email?: str, password?: str` | `None` | Start session (interactive or programmatic) |
| `login()` | - | `UserInfo` | Login to MEGA |
| `logout()` | - | `None` | Logout (alias for `log_out`) |
| `log_out()` | - | `None` | Logout and delete session |
| `disconnect()` | - | `None` | Disconnect keeping session |
| `close()` | - | `None` | Close client and release resources |
| `get_session()` | - | `Optional[SessionData]` | Get current session data |

#### File Listing

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `list_files()` | `folder?: str, refresh?: bool` | `List[MegaFile]` | List files in folder |
| `get_all_files()` | `refresh?: bool` | `List[MegaFile]` | Get all files (flat list) |
| `find()` | `name: str` | `Optional[MegaFile]` | Find file by name |

#### Tree Navigation

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_root()` | `refresh?: bool` | `MegaNode` | Get root node (Cloud Drive) |
| `get()` | `path: str, refresh?: bool` | `Optional[MegaNode]` | Get node by path |
| `cd()` | `path: str` | `MegaNode` | Change directory |
| `pwd()` | - | `str` | Get current path |
| `ls()` | `path?: str, show_hidden?: bool` | `List[MegaNode]` | List directory contents |
| `tree()` | `path?: str, max_depth?: int` | `str` | Get tree representation |
| `glob()` | `pattern: str, path?: str` | `List[MegaNode]` | Find by glob pattern |
| `walk()` | `path?: str` | `Iterator` | Walk tree like os.walk() |
| `get_node()` | `handle: str` | `Optional[MegaNode]` | Get node by handle |

#### Upload

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `upload()` | See below | `MegaFile` | Upload a file |

```python
await mega.upload(
    file_path: Union[str, Path],              # Local file path
    dest_folder: Optional[str] = None,        # Destination folder handle
    name: Optional[str] = None,               # Custom file name
    progress_callback: Optional[Callable] = None  # Progress updates
)
```

#### Download

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `download()` | `file, dest_path, progress_callback?` | `Path` | Download a file |

#### File Operations

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `delete()` | `file: Union[str, MegaFile]` | `None` | Delete file or folder |
| `rename()` | `file, new_name: str` | `None` | Rename file or folder |
| `move()` | `file, folder` | `None` | Move file to folder |
| `create_folder()` | `name: str, parent?` | `MegaFile` | Create folder |

#### Static Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `create_config()` | See below | `APIConfig` | Create configuration |

```python
MegaClient.create_config(
    proxy: Optional[str] = None,
    proxy_user: Optional[str] = None,
    proxy_pass: Optional[str] = None,
    timeout: int = 120,
    max_retries: int = 4,
    verify_ssl: bool = True,
    user_agent: Optional[str] = None
)
```

### Example: Complete Usage

```python
import asyncio
from megapy import MegaClient

async def main():
    # With custom config
    config = MegaClient.create_config(
        proxy="http://proxy:8080",
        timeout=300,
        max_retries=5
    )
    
    async with MegaClient("user@example.com", "password", config=config) as mega:
        # Get root and navigate
        root = await mega.get_root()
        print(f"Root: {root.name}")
        print(f"Children: {len(root.children)}")
        
        # Tree view
        print(await mega.tree(max_depth=3))
        
        # Navigate with cd
        await mega.cd("/Documents")
        print(f"Current: {mega.pwd()}")
        
        # List files
        files = await mega.ls()
        for f in files:
            print(f)
        
        # Find by pattern
        pdfs = await mega.glob("*.pdf")
        print(f"Found {len(pdfs)} PDFs")
        
        # Upload with progress
        def on_progress(p):
            print(f"{p.percentage:.1f}%")
        
        node = await mega.upload("report.pdf", progress_callback=on_progress)
        print(f"Uploaded: {node.name}")

asyncio.run(main())
```

---

## MegaNode

Represents a file or folder node with tree navigation capabilities.

### Constructor

Created via `MegaNodeBuilder.build_tree()` or `mega.get_root()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `handle` | `str` | Unique node identifier |
| `name` | `str` | File/folder name |
| `size` | `int` | Size in bytes |
| `is_folder` | `bool` | True if folder |
| `is_file` | `bool` | True if file |
| `is_root` | `bool` | True if root node |
| `is_empty` | `bool` | True if folder has no children |
| `node_type` | `int` | MEGA node type (0=file, 1=folder, 2=root) |
| `key` | `Optional[bytes]` | Encryption key |
| `attributes` | `Dict[str, Any]` | Decrypted attributes |
| `parent` | `Optional[MegaNode]` | Parent node |
| `children` | `List[MegaNode]` | Child nodes |
| `path` | `str` | Full path from root |
| `depth` | `int` | Depth in tree (root=0) |
| `files` | `List[MegaNode]` | Direct child files |
| `folders` | `List[MegaNode]` | Direct child folders |
| `size_formatted` | `str` | Human-readable size |

### Navigation Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `/` | `folder / "name"` | Navigate to child |
| `[]` | `folder["name"]` | Get child by name |
| `in` | `"name" in folder` | Check if child exists |
| `iter` | `for f in folder` | Iterate children |
| `len` | `len(folder)` | Number of children |

### Methods

#### Navigation

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get()` | `name: str` | `Optional[MegaNode]` | Get direct child by name |
| `find()` | `path: str` | `Optional[MegaNode]` | Find by relative path |
| `find_all()` | `name: str, recursive?: bool` | `List[MegaNode]` | Find all matching name |
| `find_by_extension()` | `ext: str, recursive?: bool` | `List[MegaNode]` | Find by extension |
| `glob()` | `pattern: str` | `List[MegaNode]` | Find by glob pattern |

#### Listing

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `ls()` | `show_hidden?: bool` | `List[MegaNode]` | List children sorted |
| `tree()` | `max_depth?: int, indent?: str` | `str` | Tree representation |
| `walk()` | - | `Iterator` | Walk like os.walk() |

#### Statistics

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_total_size()` | - | `int` | Total size including descendants |
| `count_files()` | `recursive?: bool` | `int` | Count files |
| `count_folders()` | `recursive?: bool` | `int` | Count folders |

#### Tree Operations

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `add_child()` | `node: MegaNode` | `None` | Add child node |
| `remove_child()` | `node: MegaNode` | `None` | Remove child node |

### Example: Tree Navigation

```python
import asyncio
from megapy import MegaClient

async def main():
    async with MegaClient("user@example.com", "password") as mega:
        # Get root
        root = await mega.get_root()
        
        # Navigate with / operator
        docs = root / "Documents"
        report = docs / "Reports" / "2024" / "Q1.pdf"
        
        # Check existence
        if "Documents" in root:
            print("Documents folder exists")
        
        # Iterate children
        for item in root:
            icon = "[D]" if item.is_folder else "[F]"
            print(f"{icon} {item.name} ({item.size_formatted})")
        
        # Get by index
        first = root["Documents"]
        
        # Find by path
        file = root.find("Documents/report.pdf")
        
        # Glob pattern
        all_pdfs = root.glob("**/*.pdf")
        print(f"Found {len(all_pdfs)} PDFs")
        
        # Find by extension
        images = root.find_by_extension(".jpg")
        
        # Walk like os.walk
        for folder, subfolders, files in root.walk():
            print(f"{folder.path}: {len(files)} files")
        
        # Statistics
        print(f"Total size: {root.get_total_size()} bytes")
        print(f"Total files: {root.count_files()}")
        print(f"Total folders: {root.count_folders()}")
        
        # Tree view
        print(root.tree(max_depth=3))
        # Output:
        # [+] Cloud Drive
        #   [+] Documents
        #     [-] report.pdf
        #     [-] notes.txt
        #   [+] Photos
        #     [-] vacation.jpg

asyncio.run(main())
```

---

## Custom Attributes

Extended metadata stored in the `e` (extra) object with minimized keys.

### CustomAttributes

| Property | Key | Type | Description |
|----------|-----|------|-------------|
| `document_id` | `i` | `str` | Document identifier |
| `url` | `u` | `str` | Associated URL |
| `date` | `d` | `int` | Unix timestamp |

### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `set()` | `key: str, value: Any` | `self` | Set custom key (1-2 chars) |
| `get()` | `key: str, default?` | `Any` | Get custom value |
| `to_dict()` | - | `Dict` | Convert to dict |
| `from_dict()` | `data: Dict` | `CustomAttributes` | Create from dict |

### FileAttributes

| Property | Key | Type | Description |
|----------|-----|------|-------------|
| `name` | `n` | `str` | File name (required) |
| `label` | `lbl` | `int` | Color label (0-7) |
| `is_favorite` | `fav` | `bool` | Favorite flag |
| `custom` | `e` | `CustomAttributes` | Custom attributes |

### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `to_dict()` | - | `Dict` | Convert to MEGA format |
| `from_dict()` | `data: Dict` | `FileAttributes` | Create from dict |
| `with_custom()` | `**kwargs` | `self` | Add custom attributes |

### Example: Custom Attributes

```python
from megapy.core.upload.models import FileAttributes, CustomAttributes
from datetime import datetime

# Create custom attributes
custom = CustomAttributes(
    document_id="DOC-2024-001",
    url="https://example.com/doc/001",
    date=datetime.now()
)

# Add extra custom fields (minimized keys)
custom.set('t', 'invoice')   # type
custom.set('v', 1)           # version
custom.set('c', 'client-a')  # client

print(custom.to_dict())
# {'i': 'DOC-2024-001', 'u': 'https://example.com/doc/001', 'd': 1701532800, 't': 'invoice', 'v': 1, 'c': 'client-a'}

# Create file attributes with custom
attrs = FileAttributes(
    name="invoice_001.pdf",
    label=2,  # Orange
    custom=custom
)

print(attrs.to_dict())
# {
#   'n': 'invoice_001.pdf',
#   'lbl': 2,
#   'e': {'i': 'DOC-2024-001', 'u': '...', 'd': 1701532800, 't': 'invoice', 'v': 1, 'c': 'client-a'}
# }

# Alternative: fluent API
attrs2 = FileAttributes(name="report.pdf")
attrs2.with_custom(document_id="DOC-002", url="https://test.com")
```

---

## Thumbnail & Preview Services

Auto-generation of thumbnails and previews for images and videos.

### ThumbnailService

Generates 240x240 JPEG thumbnails at 80% quality (MEGA standard).

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `generate()` | `source, crop_center?: bool` | `bytes` | Generate from image |
| `generate_from_video()` | `video_path, frame_time?: float` | `Optional[bytes]` | Generate from video |
| `is_image()` | `file_path` | `bool` | Check if image |
| `is_video()` | `file_path` | `bool` | Check if video |

### PreviewService

Generates JPEG previews with max 1024px dimension at 85% quality (MEGA standard).

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `generate()` | `source, max_size?: int` | `bytes` | Generate from image |
| `generate_from_video()` | `video_path, frame_time?: float` | `Optional[bytes]` | Generate from video |
| `get_dimensions()` | `source` | `Tuple[int, int]` | Get original dimensions |

### MediaProcessor

Automatic processing for images and videos.

| Property | Type | Description |
|----------|------|-------------|
| `auto_thumbnail` | `bool` | Auto-generate thumbnails |
| `auto_preview` | `bool` | Auto-generate previews |
| `video_frame_time` | `float` | Frame extraction time (seconds) |

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `process()` | `file_path, generate_thumbnail?, generate_preview?` | `MediaResult` | Process media file |
| `is_media()` | `file_path` | `bool` | Check if media file |
| `is_image()` | `file_path` | `bool` | Check if image |
| `is_video()` | `file_path` | `bool` | Check if video |
| `generate_thumbnail()` | `source` | `Optional[bytes]` | Generate thumbnail |
| `generate_preview()` | `source` | `Optional[bytes]` | Generate preview |

### MediaResult

| Property | Type | Description |
|----------|------|-------------|
| `thumbnail` | `Optional[bytes]` | Generated thumbnail |
| `preview` | `Optional[bytes]` | Generated preview |
| `is_media` | `bool` | True if media file |
| `media_type` | `Optional[str]` | 'image' or 'video' |

### Supported Formats

**Images**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`

**Videos**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.flv`, `.wmv`, `.m4v`

### Example: Thumbnails & Previews

```python
from megapy.core.attributes import MediaProcessor, ThumbnailService, PreviewService

# Auto-processing
processor = MediaProcessor(
    auto_thumbnail=True,
    auto_preview=True,
    video_frame_time=1.0  # Extract at 1 second
)

result = processor.process("photo.jpg")
if result.is_media:
    print(f"Thumbnail: {len(result.thumbnail)} bytes")
    print(f"Preview: {len(result.preview)} bytes")

# Manual generation
thumb_service = ThumbnailService()
preview_service = PreviewService()

# From image
thumb = thumb_service.generate("photo.jpg", crop_center=True)
preview = preview_service.generate("photo.jpg", max_size=1000)

# From video (requires ffmpeg)
thumb = thumb_service.generate_from_video("video.mp4", frame_time=2.0)
preview = preview_service.generate_from_video("video.mp4", frame_time=2.0)

# Save thumbnail
with open("thumb.jpg", "wb") as f:
    f.write(thumb)
```

---

## Upload Configuration

### UploadConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `file_path` | `Path` | required | Local file path |
| `target_folder_id` | `str` | required | Target folder handle |
| `attributes` | `FileAttributes` | auto | File attributes |
| `encryption_key` | `bytes` | auto | Custom encryption key |
| `max_concurrent_uploads` | `int` | `4` | Concurrent chunk uploads |
| `timeout` | `int` | `120` | Request timeout (seconds) |
| `thumbnail` | `bytes` | `None` | Thumbnail image (240x240 JPEG 80%) |
| `preview` | `bytes` | `None` | Preview image (max 1024px JPEG 85%) |
| `auto_thumbnail` | `bool` | `True` | Auto-generate thumbnail |
| `auto_preview` | `bool` | `True` | Auto-generate preview |
| `custom_attributes` | `CustomAttributes` | `None` | Custom attributes |

### UploadProgress

| Property | Type | Description |
|----------|------|-------------|
| `total_chunks` | `int` | Total number of chunks |
| `uploaded_chunks` | `int` | Chunks uploaded so far |
| `total_bytes` | `int` | Total file size |
| `uploaded_bytes` | `int` | Bytes uploaded so far |
| `percentage` | `float` | Upload progress (0-100) |
| `is_complete` | `bool` | True if complete |

### UploadResult

| Property | Type | Description |
|----------|------|-------------|
| `node_handle` | `str` | Created node handle |
| `file_key` | `bytes` | Encryption key |
| `file_size` | `int` | File size |
| `attributes` | `FileAttributes` | File attributes |
| `response` | `Dict` | Raw API response |
| `public_link` | `str` | Public download link |

### Example: Advanced Upload

```python
import asyncio
from megapy import MegaClient
from megapy.core.upload.models import UploadConfig, FileAttributes, CustomAttributes
from megapy.core.attributes import MediaProcessor

async def main():
    async with MegaClient("user@example.com", "password") as mega:
        # Simple upload
        node = await mega.upload("file.txt")
        
        # Upload with progress
        def on_progress(p):
            bar = "=" * int(p.percentage / 5) + ">"
            print(f"\r[{bar:21}] {p.percentage:.1f}% ({p.uploaded_bytes}/{p.total_bytes})", end="")
        
        node = await mega.upload(
            "large_file.zip",
            progress_callback=on_progress
        )
        print(f"\nUploaded: {node.name}")
        
        # Upload with custom attributes
        custom = CustomAttributes(
            document_id="INV-2024-001",
            url="https://billing.example.com/inv/001"
        )
        custom.set('t', 'invoice')
        
        attrs = FileAttributes(
            name="invoice.pdf",
            label=1,  # Red
            custom=custom
        )
        
        # Generate thumbnails for images
        processor = MediaProcessor()
        result = processor.process("photo.jpg")
        
        # Upload image with thumbnail
        config = UploadConfig(
            file_path="photo.jpg",
            target_folder_id=mega._root_id,
            attributes=FileAttributes(name="vacation.jpg"),
            thumbnail=result.thumbnail,
            preview=result.preview
        )

asyncio.run(main())
```

---

## Session Management

Telethon-style persistent sessions.

### Session Modes

```python
# Mode 1: Session-based (creates .session file)
client = MegaClient("my_account")
await client.start()  # Prompts for credentials first time

# Mode 2: Direct credentials
async with MegaClient("email", "password") as mega:
    pass

# Mode 3: Session with programmatic credentials
client = MegaClient("my_account")
await client.start(email="user@example.com", password="secret")
```

### SessionData

| Property | Type | Description |
|----------|------|-------------|
| `session_id` | `str` | Session identifier |
| `email` | `str` | User email |
| `user_id` | `str` | User ID |
| `user_name` | `str` | Display name |
| `master_key` | `bytes` | Encrypted master key |
| `private_key` | `bytes` | Encrypted private key |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

### SQLiteSession

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save()` | `data: SessionData` | `None` | Save session |
| `load()` | - | `Optional[SessionData]` | Load session |
| `delete()` | - | `None` | Delete session |
| `exists()` | - | `bool` | Check if exists |
| `close()` | - | `None` | Close connection |

### Example: Session Management

```python
import asyncio
from megapy import MegaClient, SQLiteSession
from pathlib import Path

async def main():
    # First run - login and save session
    client = MegaClient("my_account")
    await client.start()
    # Enter email: user@example.com
    # Enter password: ********
    
    files = await client.list_files()
    print(f"Found {len(files)} files")
    
    # Disconnect (keeps session)
    await client.disconnect()
    
    # Later - resume session
    client2 = MegaClient("my_account")
    await client2.start()  # No prompt - session loaded
    
    # Full logout - deletes session
    await client2.log_out()

# Custom session path
async def custom_session():
    session = SQLiteSession("account", base_path=Path("./sessions/"))
    client = MegaClient(session)
    await client.start(email="user@example.com", password="secret")
    
    # Get session info
    data = client.get_session()
    print(f"User: {data.user_name}")
    print(f"Email: {data.email}")
    print(f"Session file: {client.session_file}")

asyncio.run(main())
```

---

## Configuration

### APIConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `gateway` | `str` | `https://g.api.mega.co.nz/` | API gateway URL |
| `user_agent` | `str` | `megapy/1.0.0` | User agent string |
| `keepalive` | `bool` | `True` | Keep connection alive |
| `proxy` | `ProxyConfig` | `None` | Proxy configuration |
| `ssl` | `SSLConfig` | `None` | SSL configuration |
| `timeout` | `TimeoutConfig` | `default` | Timeout configuration |
| `retry` | `RetryConfig` | `default` | Retry configuration |
| `extra_headers` | `Dict[str, str]` | `{}` | Additional headers |
| `limit` | `int` | `100` | Connection pool limit |
| `limit_per_host` | `int` | `10` | Per-host connection limit |

### ProxyConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `url` | `str` | required | Proxy URL |
| `username` | `str` | `None` | Proxy username |
| `password` | `str` | `None` | Proxy password |

### SSLConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `verify` | `bool` | `True` | Verify SSL certificates |
| `cert_file` | `str` | `None` | Client certificate file |
| `key_file` | `str` | `None` | Client key file |
| `ca_file` | `str` | `None` | CA bundle file |
| `check_hostname` | `bool` | `True` | Verify hostname |

### TimeoutConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `total` | `float` | `300.0` | Total request timeout |
| `connect` | `float` | `30.0` | Connection timeout |
| `sock_read` | `float` | `60.0` | Socket read timeout |
| `sock_connect` | `float` | `30.0` | Socket connect timeout |

### RetryConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `max_retries` | `int` | `4` | Maximum retry attempts |
| `base_delay` | `float` | `0.25` | Initial retry delay |
| `max_delay` | `float` | `16.0` | Maximum retry delay |
| `exponential_base` | `float` | `2.0` | Exponential backoff base |

### Example: Full Configuration

```python
from megapy import (
    MegaClient, APIConfig, ProxyConfig, 
    SSLConfig, TimeoutConfig, RetryConfig
)

config = APIConfig(
    gateway='https://g.api.mega.co.nz/',
    user_agent='my-app/2.0.0',
    
    proxy=ProxyConfig(
        url='http://proxy.example.com:8080',
        username='user',
        password='pass'
    ),
    
    ssl=SSLConfig(
        verify=True,
        check_hostname=True,
        cert_file='/path/to/cert.pem',
        ca_file='/path/to/ca.pem'
    ),
    
    timeout=TimeoutConfig(
        total=300.0,
        connect=30.0,
        sock_read=60.0,
        sock_connect=30.0
    ),
    
    retry=RetryConfig(
        max_retries=5,
        base_delay=1.0,
        max_delay=32.0,
        exponential_base=2.0
    ),
    
    extra_headers={
        'X-Custom-Header': 'value'
    },
    
    limit_per_host=20,
    limit=200
)

async with MegaClient("email", "password", config=config) as mega:
    files = await mega.list_files()
```

---

## Error Handling

```python
from megapy.core.api import MegaAPIError

try:
    async with MegaClient(email, password) as mega:
        await mega.upload("file.txt")
except MegaAPIError as e:
    print(f"API Error: {e.code} - {e.message}")
except FileNotFoundError as e:
    print(f"File not found: {e}")
except RuntimeError as e:
    print(f"Runtime error: {e}")
```

---

## Complete Examples

### Backup Script

```python
import asyncio
from pathlib import Path
from megapy import MegaClient

async def backup_folder(local_path: str, mega_folder: str = None):
    async with MegaClient("user@example.com", "password") as mega:
        folder = Path(local_path)
        
        for file in folder.rglob("*"):
            if file.is_file():
                print(f"Uploading: {file.name}")
                await mega.upload(file, dest_folder=mega_folder)

asyncio.run(backup_folder("./my_documents"))
```

### File Sync Script

```python
import asyncio
from pathlib import Path
from megapy import MegaClient

async def sync_from_mega(local_dir: str):
    async with MegaClient("user@example.com", "password") as mega:
        root = await mega.get_root()
        
        for folder, subfolders, files in root.walk():
            # Create local folder structure
            local_path = Path(local_dir) / folder.path.lstrip("/")
            local_path.mkdir(parents=True, exist_ok=True)
            
            # Download files
            for file in files:
                dest = local_path / file.name
                if not dest.exists():
                    print(f"Downloading: {file.path}")
                    await mega.download(file, str(local_path))

asyncio.run(sync_from_mega("./mega_backup"))
```

### Document Management

```python
import asyncio
from datetime import datetime
from megapy import MegaClient
from megapy.core.upload.models import FileAttributes, CustomAttributes

async def upload_invoice(file_path: str, invoice_id: str, client_name: str):
    async with MegaClient("user@example.com", "password") as mega:
        # Create custom attributes
        custom = CustomAttributes(
            document_id=invoice_id,
            url=f"https://billing.example.com/invoices/{invoice_id}",
            date=datetime.now()
        )
        custom.set('c', client_name)  # client
        custom.set('t', 'invoice')    # type
        custom.set('s', 'pending')    # status
        
        # Create file attributes
        attrs = FileAttributes(
            name=f"INV_{invoice_id}.pdf",
            label=1,  # Red
            custom=custom
        )
        
        # Upload
        node = await mega.upload(file_path, name=attrs.name)
        print(f"Uploaded invoice {invoice_id}")
        
        return node

asyncio.run(upload_invoice("invoice.pdf", "2024-001", "ACME Corp"))
```

### Photo Gallery with Thumbnails

```python
import asyncio
from pathlib import Path
from megapy import MegaClient
from megapy.core.attributes import MediaProcessor

async def upload_photos(photos_dir: str):
    processor = MediaProcessor()
    
    async with MegaClient("user@example.com", "password") as mega:
        photos = Path(photos_dir)
        
        for photo in photos.glob("*.jpg"):
            # Generate thumbnail and preview
            result = processor.process(photo)
            
            if result.is_media:
                print(f"Uploading {photo.name}...")
                print(f"  Thumbnail: {len(result.thumbnail)} bytes")
                print(f"  Preview: {len(result.preview)} bytes")
                
                # Upload with generated images
                await mega.upload(photo)

asyncio.run(upload_photos("./my_photos"))
```

---

## Testing

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run e2e tests
python tests/e2e/test_tree_navigation.py
python tests/e2e/test_custom_attributes.py

# Run with coverage
python -m pytest tests/unit/ --cov=megapy --cov-report=html
```

---

## Project Structure

```
megapy/
├── __init__.py              # Main exports
├── client.py                # MegaClient (high-level API)
├── nodes.py                 # MegaNode tree navigation
└── core/
    ├── api/                 # API client and auth
    ├── attributes/          # Custom attributes, thumbnails
    ├── crypto/              # AES, RSA, hashing
    ├── session/             # Session persistence
    ├── storage/             # Node storage and processing
    └── upload/              # Upload coordinator
```

---

## License

MIT License

---

**Built with SOLID principles and modern async Python**
