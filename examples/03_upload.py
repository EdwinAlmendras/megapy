"""
Upload files to MEGA
"""
import asyncio
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        
        # Simple upload to root
        node = await mega.upload("document.pdf")
        print(f"Uploaded: {node}")
        
        # Upload with custom name
        node = await mega.upload("photo.jpg", name="vacation_2024.jpg")
        print(f"Uploaded as: {node.name}")
        
        # Upload to specific folder
        docs = await mega.find("Documents")
        if docs:
            node = await mega.upload("report.pdf", dest_folder=docs.handle)
            print(f"Uploaded to Documents: {node}")
        
        # Upload with progress callback
        def on_progress(progress):
            pct = (progress.bytes_sent / progress.total_bytes) * 100
            print(f"Progress: {pct:.1f}%")
        
        node = await mega.upload("large_file.zip", progress_callback=on_progress)
        print(f"Uploaded: {node}")
        
        # Upload with custom attributes
        node = await mega.upload("invoice.pdf", custom={
            'i': 'INV-001',      # Document ID
            'u': 'https://...',  # URL reference
            't': 'invoice'       # Custom tag
        })
        print(f"Uploaded with attrs: {node}")
        
        # Upload image (auto-generates thumbnail & preview)
        node = await mega.upload("photo.jpg")  # auto_thumb=True by default
        print(f"Uploaded image: {node}")
        print(f"Has thumbnail: {node.has_thumbnail}")
        print(f"Has preview: {node.has_preview}")
        
        # Upload video (auto-extracts media info)
        node = await mega.upload("video.mp4")
        if node.has_media_info:
            info = node.media_info
            print(f"Video: {info.width}x{info.height}, {info.playtime}s")


if __name__ == "__main__":
    asyncio.run(main())
