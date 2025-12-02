"""
E2E Test: Simple API usage.

Demonstrates the simplified MegaClient API.
"""
import sys
import os
import asyncio
import logging
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Silence verbose loggers
logging.getLogger('megapy.api').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

logger = logging.getLogger('test')


async def test_simple_usage():
    """
    Test the simplified MegaClient API.
    
    Shows how easy it is to use megapy now!
    """
    from megapy import MegaClient
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("=" * 60)
    logger.info("MegaPy Simple API Test")
    logger.info("=" * 60)
    
    # Super simple usage with context manager
    async with MegaClient(email, password) as mega:
        
        # 1. List files
        logger.info("\n[LIST] Listing files...")
        files = await mega.list_files()
        
        for f in files:
            logger.info(f"   {f}")
        
        logger.info(f"\n   Total: {len(files)} files/folders")
        
        # 2. Upload a file
        logger.info("\n[UPLOAD] Uploading README.md...")
        
        readme_path = Path(__file__).parent.parent.parent / "README.md"
        
        def on_progress(progress):
            logger.info(f"   Progress: {progress.percentage:.0f}%")
        
        uploaded = await mega.upload(
            readme_path,
            name="test_simple_api.md",
            progress_callback=on_progress
        )
        
        logger.info(f"   OK - Uploaded: {uploaded.name} (handle: {uploaded.handle})")
        
        # 3. Find the file
        logger.info("\n[FIND] Finding uploaded file...")
        found = await mega.find("test_simple_api.md")
        
        if found:
            logger.info(f"   OK - Found: {found}")
        else:
            logger.error("   FAIL - File not found!")
            return False
        
        # 4. Get all files
        logger.info("\n[ALL] Getting all files...")
        all_files = await mega.get_all_files()
        logger.info(f"   Total files in account: {len(all_files)}")
        
        # 5. Delete the test file
        logger.info("\n[DELETE] Cleaning up...")
        await mega.delete(uploaded)
        logger.info("   OK - Test file deleted")
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST PASSED - Simple API works perfectly!")
    logger.info("=" * 60)
    
    return True


async def test_with_custom_config():
    """
    Test with custom configuration.
    """
    from megapy import MegaClient
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("\n" + "=" * 60)
    logger.info("Custom Configuration Test")
    logger.info("=" * 60)
    
    # Create custom configuration
    config = MegaClient.create_config(
        timeout=120,
        max_retries=3,
        user_agent='my-app/2.0.0'
    )
    
    logger.info(f"   Timeout: {config.timeout.total}s")
    logger.info(f"   Retries: {config.retry.max_retries}")
    logger.info(f"   User-Agent: {config.user_agent}")
    
    # Use with custom config
    async with MegaClient(email, password, config=config) as mega:
        files = await mega.list_files()
        logger.info(f"\n   Listed {len(files)} files with custom config")
    
    logger.info("\nOK - Custom configuration works!")
    
    return True


async def demo_api():
    """
    Demonstrates all API features.
    """
    logger.info("\n" + "=" * 60)
    logger.info("API Features Demo")
    logger.info("=" * 60)
    
    logger.info("""
    MegaClient API Reference:

    # Basic usage
    async with MegaClient(email, password) as mega:
        
        # List files in root
        files = await mega.list_files()
        
        # List files in folder
        files = await mega.list_files(folder_handle)
        
        # Get all files (flat)
        all_files = await mega.get_all_files()
        
        # Find by name
        file = await mega.find("document.pdf")
        
        # Upload
        node = await mega.upload("local_file.txt")
        node = await mega.upload("file.txt", name="custom_name.txt")
        node = await mega.upload("file.txt", dest_folder=folder_handle)
        
        # Download
        path = await mega.download("remote_file.txt")
        path = await mega.download("file.txt", "./downloads/")
        path = await mega.download(mega_file, "./")
        
        # Delete
        await mega.delete("file.txt")
        await mega.delete(mega_file)
        
        # Rename
        await mega.rename("old_name.txt", "new_name.txt")
        
        # Move
        await mega.move("file.txt", "folder_name")
        
        # Create folder
        folder = await mega.create_folder("New Folder")
        folder = await mega.create_folder("Subfolder", parent=folder)

    # With custom config
    config = MegaClient.create_config(
        proxy="http://proxy:8080",
        timeout=60,
        max_retries=5,
        verify_ssl=True
    )
    
    async with MegaClient(email, password, config=config) as mega:
        ...
    """)
    
    return True


def main():
    """Run all tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Demo API
        loop.run_until_complete(demo_api())
        
        # Test custom config
        result1 = loop.run_until_complete(test_with_custom_config())
        
        # Test simple usage
        result2 = loop.run_until_complete(test_simple_usage())
        
        return result1 and result2
        
    finally:
        loop.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
