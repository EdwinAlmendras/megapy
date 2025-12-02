# MegaPy Examples

## Quick Start

```python
from megapy import MegaClient
import asyncio

async def main():
    async with MegaClient("session") as mega:
        root = await mega.get_root()
        for node in root:
            print(node)

asyncio.run(main())
```

## Examples

| File | Description |
|------|-------------|
| `01_basic.py` | Login and list files |
| `02_filesystem.py` | Navigate folders, search files |
| `03_upload.py` | Upload files with options |
| `04_download.py` | Download files |
| `05_media_info.py` | Video/audio metadata |
| `06_file_operations.py` | Create, rename, move, delete |
| `07_sessions.py` | Login persistence |
| `08_advanced.py` | Proxy, config, batch ops |

## API Reference

### Navigation

```python
root = await mega.get_root()     # Get root folder
node = await mega.get("/path")   # Get by path
node = await mega.find("name")   # Find by name

# Navigate with /
docs = root / "Documents"
file = docs / "report.pdf"

# Iterate
for node in root:           # Direct children
    print(node)

for node in root.walk():    # All descendants
    print(node.path)
```

### Properties

```python
node.name           # File name
node.size           # Size in bytes
node.path           # Full path
node.is_file        # True if file
node.is_folder      # True if folder
node.files          # Child files
node.folders        # Child folders
node.children       # All children
node.parent         # Parent node
```

### Media Info

```python
# Optional: Load codec names from MEGA API
await mega.load_codecs()

if node.has_media_info:
    info = node.media_info
    info.playtime          # Duration (seconds)
    info.duration_formatted # "1:23" or "1:23:45"
    info.width             # Video width
    info.height            # Video height
    info.resolution        # "1920x1080"
    info.fps               # Frames per second
    info.codec_string      # "mp4/h264/aac"
    info.container_name    # "mp4", "mkv", etc.
    info.video_codec_name  # "h264", "hevc", etc.
    info.audio_codec_name  # "aac", "mp3", etc.
    info.is_video          # True if video
    info.is_audio          # True if audio-only
```

### Operations

```python
await mega.upload("file.pdf")
await mega.download(node, "./")
await mega.delete(node)
await mega.rename(node, "new.pdf")
await mega.move(node, folder)
await mega.create_folder("Name")
```
