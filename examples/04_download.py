"""
Download files from MEGA
"""
import asyncio
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        root = await mega.get_root()
        
        # Find a file
        node = await mega.find("document.pdf")
        if not node:
            print("File not found")
            return
        
        # Download to current directory
        path = await mega.download(node)
        print(f"Downloaded to: {path}")
        
        # Download to specific directory
        path = await mega.download(node, dest_path="./downloads")
        print(f"Downloaded to: {path}")
        
        # Download with progress
        def on_progress(downloaded, total):
            pct = (downloaded / total) * 100
            print(f"Progress: {pct:.1f}%")
        
        path = await mega.download(node, progress_callback=on_progress)
        print(f"Done: {path}")
        
        # Download using node method
        path = await node.download("./")
        print(f"Downloaded: {path}")
        
        # Download by name (string)
        path = await mega.download("video.mp4", dest_path="./videos")
        print(f"Downloaded: {path}")


if __name__ == "__main__":
    asyncio.run(main())
