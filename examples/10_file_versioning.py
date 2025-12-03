"""
Example 10: File Versioning (Update)

This example shows how to update existing files in MEGA,
creating new versions while preserving the old ones.
"""
import asyncio
from pathlib import Path
from megapy import MegaClient


async def main():
    """Basic file update example."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        # First, upload an initial file
        print("Uploading initial version...")
        file_v1 = await mega.upload("report_v1.txt", name="report.txt")
        print(f"  v1 uploaded: {file_v1.handle}")
        
        # Update the file with new content
        print("\nUpdating with new content...")
        file_v2 = await mega.update(file_v1, "report_v2.txt")
        print(f"  v2 uploaded: {file_v2.handle}")
        
        # Update again
        print("\nUpdating again...")
        file_v3 = await mega.update(file_v2, "report_v3.txt")
        print(f"  v3 uploaded: {file_v3.handle}")
        
        print("\nDone! Check MEGA's version history to see all versions.")


async def update_by_path():
    """Update a file by its MEGA path."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        # Update file using its path in MEGA
        new_version = await mega.update(
            "/Documents/report.pdf",  # Existing file path
            "updated_report.pdf"       # Local file with new content
        )
        
        print(f"Updated! New version: {new_version.handle}")


async def update_with_rename():
    """Update a file and change its name."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        # Get the existing file
        old_file = await mega.get("/Documents/data.csv")
        
        if old_file:
            # Update with new content and new name
            new_version = await mega.update(
                old_file,
                "quarterly_data.csv",
                name="Q4_2024_data.csv"  # New name
            )
            print(f"Updated and renamed to: {new_version.name}")


async def update_with_progress():
    """Update a large file with progress tracking."""
    from megapy import UploadProgress
    
    def on_progress(p: UploadProgress):
        pct = p.percentage
        uploaded = p.uploaded_bytes
        total = p.total_bytes
        print(f"\rUpdating: {pct:.1f}% ({uploaded}/{total} bytes)", end="")
    
    async with MegaClient("session") as mega:
        await mega.start()
        
        # Update with progress callback
        new_version = await mega.update(
            "/Backups/database.sql",
            "database_backup.sql",
            progress_callback=on_progress
        )
        
        print(f"\nUpdate complete! New handle: {new_version.handle}")


async def update_image_with_thumbnail():
    """Update an image file (thumbnails auto-generated)."""
    async with MegaClient("session") as mega:
        await mega.start()
        
        # When updating images/videos, thumbnails are auto-generated
        new_version = await mega.update(
            "/Photos/profile.jpg",
            "new_profile.jpg",
            auto_thumb=True  # Default is True
        )
        
        print(f"Image updated with new thumbnail!")
        print(f"  Has thumbnail: {new_version.has_thumbnail}")
        print(f"  Has preview: {new_version.has_preview}")


if __name__ == "__main__":
    asyncio.run(main())
