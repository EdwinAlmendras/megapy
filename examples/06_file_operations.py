"""
File operations - Create, rename, move, delete
"""
import asyncio
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        
        # Create folder
        folder = await mega.create_folder("My New Folder")
        print(f"Created: {folder}")
        
        # Create nested folder
        subfolder = await mega.create_folder("Subfolder", parent=folder)
        print(f"Created: {subfolder}")
        
        # Rename file
        node = await mega.find("old_name.pdf")
        if node:
            renamed = await mega.rename(node, "new_name.pdf")
            print(f"Renamed to: {renamed.name}")
        
        # Move file to folder
        file = await mega.find("document.pdf")
        folder = await mega.find("Documents")
        if file and folder:
            await mega.move(file, folder)
            print(f"Moved {file.name} to {folder.name}")
        
        # Delete file
        node = await mega.find("temp_file.txt")
        if node:
            await mega.delete(node)
            print("Deleted!")
        
        # Using node methods directly
        node = await mega.find("file.txt")
        if node:
            await node.rename("renamed.txt")
            await node.delete()


if __name__ == "__main__":
    asyncio.run(main())
