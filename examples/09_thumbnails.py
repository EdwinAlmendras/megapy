"""
Example 09: Downloading Thumbnails and Previews

This example shows how to download thumbnails and previews
from files stored in MEGA.
"""
import asyncio
from pathlib import Path
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        await mega.start()
        
        root = await mega.get_root()
        
        # Create output directory
        output_dir = Path("thumbnails")
        output_dir.mkdir(exist_ok=True)
        
        print("Scanning for files with thumbnails/previews...\n")
        
        for node in root.walk():
            if node.is_folder:
                continue
            
            # Check if file has thumbnail
            if node.has_thumbnail:
                print(f"[THUMB] {node.name}")
                
                # Download thumbnail (240x240 JPEG)
                thumb_data = await node.get_thumbnail()
                if thumb_data:
                    thumb_path = output_dir / f"{node.handle}_thumb.jpg"
                    with open(thumb_path, "wb") as f:
                        f.write(thumb_data)
                    print(f"  -> Saved: {thumb_path} ({len(thumb_data)} bytes)")
            
            # Check if file has preview
            if node.has_preview:
                print(f"[PREVIEW] {node.name}")
                
                # Download preview (max 1024px JPEG)
                preview_data = await node.get_preview()
                if preview_data:
                    preview_path = output_dir / f"{node.handle}_preview.jpg"
                    with open(preview_path, "wb") as f:
                        f.write(preview_data)
                    print(f"  -> Saved: {preview_path} ({len(preview_data)} bytes)")
        
        print(f"\nDone! Check the '{output_dir}' folder.")


async def download_single_thumbnail():
    """Download thumbnail from a specific file."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        # Get file by path
        node = await mega.get("/Photos/vacation.jpg")
        
        if node and node.has_thumbnail:
            thumb = await node.get_thumbnail()
            if thumb:
                with open("vacation_thumb.jpg", "wb") as f:
                    f.write(thumb)
                print("Thumbnail saved!")
        else:
            print("File has no thumbnail")


async def list_files_with_thumbnails():
    """List all files that have thumbnails."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        root = await mega.get_root()
        
        files_with_thumb = []
        files_with_preview = []
        
        for node in root.walk():
            if node.is_file:
                if node.has_thumbnail:
                    files_with_thumb.append(node)
                if node.has_preview:
                    files_with_preview.append(node)
        
        print(f"Files with thumbnails: {len(files_with_thumb)}")
        for f in files_with_thumb[:10]:  # Show first 10
            print(f"  - {f.path}")
        
        print(f"\nFiles with previews: {len(files_with_preview)}")
        for f in files_with_preview[:10]:
            print(f"  - {f.path}")


if __name__ == "__main__":
    asyncio.run(main())
