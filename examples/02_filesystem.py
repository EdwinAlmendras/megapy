"""
Filesystem navigation - Browse folders and files
"""
import asyncio
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        root = await mega.get_root()
        
        # Navigate with / operator
        docs = root / "Documents"
        if docs:
            print(f"Found: {docs.path}")
            file = docs / "report.pdf"
            if file:
                print(f"Found file: {file.name}")
        
        # Iterate children
        print("\n--- Direct children ---")
        for node in root:
            icon = "[DIR]" if node.is_folder else "[FILE]"
            print(f"{icon} {node.name}")
        
        # Recursive walk (all files)
        print("\n--- All files (recursive) ---")
        for node in root.walk():
            print(f"  {node.path}")
        
        # Get only files or folders
        print(f"\n--- Summary ---")
        print(f"Files in root: {len(root.files)}")
        print(f"Folders in root: {len(root.folders)}")
        
        # Find by path
        node = await mega.get("/Documents/report.pdf")
        if node:
            print(f"\nFound by path: {node}")
        
        # Find by name
        node = await mega.find("video.mp4")
        if node:
            print(f"Found by name: {node}")


if __name__ == "__main__":
    asyncio.run(main())
