"""
Basic usage - Login and list files
"""
import asyncio
from megapy import MegaClient


async def main():
    # Session mode (saves credentials to session.session file)
    async with MegaClient("session") as mega:
        
        # Get root folder
        root = await mega.get_root()
        print(f"Connected! Root: {root.name}")
        
        # List all items in root
        print("\nFiles in root:")
        for node in root:
            print(f"  {node}")


if __name__ == "__main__":
    asyncio.run(main())
