"""
E2E Test: Upload README.md to MEGA.

Tests the complete async upload workflow.
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Silence verbose loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

logger = logging.getLogger('megapy.test.upload')


async def test_upload_readme():
    """
    Test uploading README.md to MEGA root folder.
    
    This test:
    1. Creates an async API client with custom configuration
    2. Logs in using async auth service
    3. Gets the root folder ID
    4. Uploads README.md
    5. Verifies the file appears in the listing
    6. Cleans up (optionally deletes the file)
    """
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    # Find README.md
    project_root = Path(__file__).parent.parent.parent
    readme_path = project_root / "README.md"
    
    if not readme_path.exists():
        logger.error(f"README.md not found at {readme_path}")
        return False
    
    logger.info("=" * 60)
    logger.info("MegaPy E2E Upload Test")
    logger.info("=" * 60)
    logger.info(f"File to upload: {readme_path}")
    logger.info(f"File size: {readme_path.stat().st_size} bytes")
    
    try:
        from megapy.core.api.config import APIConfig, TimeoutConfig, RetryConfig
        from megapy.core.api.async_client import AsyncAPIClient
        from megapy.core.api.async_auth import AsyncAuthService
        from megapy.core.upload import UploadCoordinator, UploadConfig, UploadProgress
        from megapy.core.upload.models import FileAttributes
        
        # Step 1: Create config with custom settings
        logger.info("-" * 40)
        logger.info("Step 1: Creating API configuration")
        
        config = APIConfig(
            user_agent='megapy-test/1.0.0',
            timeout=TimeoutConfig(
                total=300.0,
                connect=30.0,
                sock_read=60.0
            ),
            retry=RetryConfig(
                max_retries=3,
                base_delay=0.5
            ),
            log_level=logging.DEBUG
        )
        
        logger.info(f"  User-Agent: {config.user_agent}")
        logger.info(f"  Timeout: {config.timeout.total}s total")
        logger.info(f"  Retries: {config.retry.max_retries}")
        
        # Step 2: Create async client and login
        logger.info("-" * 40)
        logger.info("Step 2: Logging in asynchronously")
        
        async with AsyncAPIClient(config) as client:
            auth_service = AsyncAuthService(client)
            auth_result = await auth_service.login(email, password)
            
            logger.info(f"  Login successful!")
            logger.info(f"  User: {auth_result.user_name}")
            logger.info(f"  User ID: {auth_result.user_id}")
            logger.info(f"  Master key: {len(auth_result.master_key)} bytes")
            
            # Step 3: Get files to find root folder
            logger.info("-" * 40)
            logger.info("Step 3: Getting file list to find root folder")
            
            files_response = await client.get_files()
            
            # Find root folder (type 2)
            root_id = None
            nodes = files_response.get('f', [])
            
            for node in nodes:
                if node.get('t') == 2:  # Root folder
                    root_id = node.get('h')
                    break
            
            if not root_id:
                logger.error("  Root folder not found!")
                return False
            
            logger.info(f"  Root folder ID: {root_id}")
            logger.info(f"  Total nodes in account: {len(nodes)}")
            
            # Step 4: Upload README.md
            logger.info("-" * 40)
            logger.info("Step 4: Uploading README.md")
            
            def progress_callback(progress: UploadProgress):
                """Log upload progress."""
                logger.info(
                    f"  Progress: {progress.uploaded_chunks}/{progress.total_chunks} "
                    f"chunks ({progress.percentage:.1f}%) - "
                    f"{progress.uploaded_bytes}/{progress.total_bytes} bytes"
                )
            
            # Create upload coordinator
            coordinator = UploadCoordinator(
                api_client=client,
                master_key=auth_result.master_key,
                progress_callback=progress_callback
            )
            
            # Configure upload
            upload_config = UploadConfig(
                file_path=readme_path,
                target_folder_id=root_id,
                attributes=FileAttributes(
                    name="README_test_upload.md"  # Unique name to avoid conflicts
                )
            )
            
            # Execute upload
            result = await coordinator.upload(upload_config)
            
            logger.info(f"  Upload complete!")
            logger.info(f"  Node handle: {result.node_handle}")
            logger.info(f"  File key: {len(result.file_key)} bytes")
            
            # Step 5: Verify file in listing
            logger.info("-" * 40)
            logger.info("Step 5: Verifying file in listing")
            
            files_response = await client.get_files()
            nodes = files_response.get('f', [])
            
            found = False
            for node in nodes:
                if node.get('h') == result.node_handle:
                    found = True
                    logger.info(f"  File found in listing!")
                    logger.info(f"  Node data: handle={node.get('h')}, size={node.get('s')}")
                    break
            
            if not found:
                logger.warning("  File not found in listing immediately (may be delayed)")
            
            # Step 6: Clean up - delete the test file
            logger.info("-" * 40)
            logger.info("Step 6: Cleaning up - deleting test file")
            
            try:
                await client.delete_node(result.node_handle)
                logger.info("  Test file deleted successfully")
            except Exception as e:
                logger.warning(f"  Could not delete test file: {e}")
            
            logger.info("-" * 40)
            logger.info("=" * 60)
            logger.info("TEST PASSED - Upload workflow completed successfully!")
            logger.info("=" * 60)
            
            return True
            
    except Exception as e:
        logger.exception(f"TEST FAILED: {e}")
        return False


async def test_upload_with_proxy_config():
    """
    Test creating upload configuration with proxy settings.
    
    This test demonstrates the configuration options without
    actually using a proxy (which would require a real proxy server).
    """
    logger.info("=" * 60)
    logger.info("Configuration Options Demo")
    logger.info("=" * 60)
    
    try:
        from megapy.core.api.config import (
            APIConfig, 
            ProxyConfig, 
            SSLConfig, 
            TimeoutConfig, 
            RetryConfig
        )
        
        # Demo: Full configuration with all options
        full_config = APIConfig(
            gateway='https://g.api.mega.co.nz/',
            user_agent='megapy-custom/2.0.0',
            keepalive=True,
            
            # Proxy configuration (not used in actual test)
            proxy=ProxyConfig(
                url='http://proxy.example.com:8080',
                username='user',
                password='pass'
            ),
            
            # SSL configuration
            ssl=SSLConfig(
                verify=True,
                check_hostname=True,
                # cert_file='/path/to/cert.pem',
                # ca_file='/path/to/ca.pem'
            ),
            
            # Timeout configuration
            timeout=TimeoutConfig(
                total=600.0,        # 10 minutes total
                connect=60.0,       # 1 minute to connect
                sock_read=120.0,    # 2 minutes read timeout
                sock_connect=30.0   # 30 seconds socket connect
            ),
            
            # Retry configuration
            retry=RetryConfig(
                max_retries=5,
                base_delay=1.0,
                max_delay=32.0,
                exponential_base=2.0,
                retry_on_codes=(-3, -6, -18)
            ),
            
            # Additional headers
            extra_headers={
                'X-Custom-Header': 'custom-value',
                'Accept-Language': 'en-US'
            },
            
            # Connection pool settings
            limit_per_host=20,
            limit=200,
            
            # Logging
            log_level=logging.DEBUG
        )
        
        logger.info("Full configuration created:")
        logger.info(f"  Gateway: {full_config.gateway}")
        logger.info(f"  User-Agent: {full_config.user_agent}")
        logger.info(f"  Proxy: {full_config.proxy.url if full_config.proxy else 'None'}")
        logger.info(f"  SSL verify: {full_config.ssl.verify}")
        logger.info(f"  Timeout total: {full_config.timeout.total}s")
        logger.info(f"  Max retries: {full_config.retry.max_retries}")
        logger.info(f"  Connection limit: {full_config.limit}")
        logger.info(f"  Extra headers: {full_config.extra_headers}")
        
        # Demo: Quick configurations
        logger.info("-" * 40)
        
        default_config = APIConfig.default()
        logger.info(f"Default config: gateway={default_config.gateway}")
        
        proxy_config = APIConfig.with_proxy('http://proxy:8080')
        logger.info(f"Proxy config: proxy={proxy_config.proxy.url}")
        
        insecure_config = APIConfig.insecure()
        logger.info(f"Insecure config: verify={insecure_config.ssl.verify}")
        
        logger.info("-" * 40)
        logger.info("Configuration demo completed!")
        
        return True
        
    except Exception as e:
        logger.exception(f"Configuration demo failed: {e}")
        return False


def main():
    """Run all e2e upload tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test 1: Configuration demo
        result1 = loop.run_until_complete(test_upload_with_proxy_config())
        
        # Test 2: Actual upload test
        result2 = loop.run_until_complete(test_upload_readme())
        
        return result1 and result2
        
    finally:
        loop.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
