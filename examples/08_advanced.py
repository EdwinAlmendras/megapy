"""
Advanced usage - Proxy, config, batch operations
"""
import asyncio
from megapy import MegaClient


async def main():
    # Custom configuration
    config = MegaClient.create_config(
        proxy="http://proxy.example.com:8080",
        proxy_user="user",
        proxy_pass="pass",
        timeout=60,
        max_retries=3,
        verify_ssl=True
    )
    
    async with MegaClient("session", config=config) as mega:
        root = await mega.get_root()
        
        # Batch download all PDFs
        for node in root.walk():
            if node.name.endswith(".pdf"):
                await mega.download(node, "./pdfs")
                print(f"Downloaded: {node.name}")
        
        # Find all videos larger than 100MB
        large_videos = [
            node for node in root.walk()
            if node.is_video and node.size > 100 * 1024 * 1024
        ]
        print(f"Found {len(large_videos)} large videos")
        
        # Get storage info
        info = await mega.get_user_info()
        print(f"User: {info.email}")
        print(f"Used: {info.used_storage / 1e9:.2f} GB")
        print(f"Total: {info.total_storage / 1e9:.2f} GB")
        print(f"Free: {info.free_storage / 1e9:.2f} GB")


if __name__ == "__main__":
    asyncio.run(main())
