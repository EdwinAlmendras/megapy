"""
Example usage of the MEGA Upload module.

This script demonstrates how to use the MegaUploader class to upload files to MEGA.
"""
import asyncio
import os
from pathlib import Path
import logging
from mega_py.api import MegaApi
from upload import MegaUploader
from utils.logger import setup_logger

async def main() -> None:
    """
    Main function demonstrating upload to MEGA.
    
    This example:
    1. Creates a MEGA API client
    2. Initializes a MegaUploader
    3. Uploads a file to a target folder
    """
    # Setup logger
    logger = setup_logger("MegaUploadExample", logging.DEBUG)
    logger.info("Starting MEGA upload example")
    
    # MEGA account credentials
    email = os.environ.get("MEGA_EMAIL")
    password = os.environ.get("MEGA_PASSWORD")
    
    if not email or not password:
        logger.error("MEGA_EMAIL and MEGA_PASSWORD environment variables must be set")
        return
    
    try:
        # Initialize MEGA API client
        api = MegaApi(email, password)
        await api.login()
        
        # Get master key and root folder ID
        master_key = api.master_key
        root_folder_id = api.root_id
        
        # Initialize uploader
        uploader = MegaUploader(api, master_key, logger=logger)
        
        # File to upload
        file_path = Path("example_file.txt")
        
        # Check if the file exists, create a test file if not
        if not file_path.exists():
            logger.info(f"Creating test file: {file_path}")
            with open(file_path, "w") as f:
                f.write("This is a test file for MEGA upload.\n" * 1000)
        
        # Custom attributes
        attributes = {
            "name": file_path.name,
            "description": "Test file uploaded using the new MegaUploader"
        }
        
        # Upload file
        logger.info(f"Uploading {file_path} to MEGA")
        result = await uploader.upload(
            file_path=file_path,
            target_folder_id=root_folder_id,
            attributes=attributes,
            max_concurrent_uploads=3
        )
        
        # Display result
        logger.info(f"Upload successful: {result}")
        
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}")
    finally:
        # Logout
        if 'api' in locals() and api:
            await api.logout()

if __name__ == "__main__":
    asyncio.run(main()) 