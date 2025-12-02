"""
E2E Test: Session persistence and resume.

Tests the complete session workflow with a real MEGA account.
"""
import sys
import os
import asyncio
import logging
import tempfile
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger('megapy.api').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

logger = logging.getLogger('test.session')


async def test_session_persistence():
    """
    Test session persistence and resume.
    
    1. Login with credentials and save session
    2. Close client
    3. Resume session without credentials
    4. Verify we can still access files
    """
    from megapy import MegaClient, SQLiteSession
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("=" * 60)
    logger.info("Session Persistence Test")
    logger.info("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        session_path = Path(tmpdir)
        
        # =====================================================================
        # Step 1: First login - create session
        # =====================================================================
        logger.info("\n[STEP 1] First login - creating session...")
        
        client1 = MegaClient("test_account", config=MegaClient.create_config(), base_path=session_path)
        
        try:
            # Start with credentials
            await client1.start(email=email, password=password)
            
            logger.info(f"   Logged in successfully")
            logger.info(f"   Session file: {client1.session_file}")
            
            # Verify session file exists
            session_file = session_path / "test_account.session"
            assert session_file.exists(), "Session file should exist"
            logger.info(f"   Session file created: {session_file.stat().st_size} bytes")
            
            # List files to verify working
            files = await client1.list_files()
            file_count = len(files)
            logger.info(f"   Files in account: {file_count}")
            
            # Get session data
            session_data = client1.get_session()
            assert session_data is not None, "Session data should exist"
            logger.info(f"   Session email: {session_data.email}")
            logger.info(f"   Session user: {session_data.user_name}")
            logger.info(f"   Session ID: {session_data.session_id[:20]}...")
            
        finally:
            await client1.disconnect()
        
        logger.info("   Client 1 disconnected")
        
        # =====================================================================
        # Step 2: Resume session - no credentials needed
        # =====================================================================
        logger.info("\n[STEP 2] Resuming session - no credentials...")
        
        client2 = MegaClient("test_account", base_path=session_path)
        
        try:
            # Start WITHOUT credentials - should resume
            await client2.start()
            
            logger.info("   Session resumed successfully!")
            
            # Verify we can still access files
            files = await client2.list_files()
            assert len(files) == file_count, "Should see same number of files"
            logger.info(f"   Files in account: {len(files)}")
            
            # Verify session data is same
            session_data = client2.get_session()
            assert session_data.email == email, "Email should match"
            logger.info(f"   Session verified for: {session_data.email}")
            
        finally:
            await client2.disconnect()
        
        logger.info("   Client 2 disconnected")
        
        # =====================================================================
        # Step 3: Third connection - verify persistence
        # =====================================================================
        logger.info("\n[STEP 3] Third connection - verify persistence...")
        
        client3 = MegaClient("test_account", base_path=session_path)
        
        try:
            await client3.start()
            
            # Upload a file to prove full functionality
            readme_path = Path(__file__).parent.parent.parent / "README.md"
            
            logger.info("   Uploading test file...")
            node = await client3.upload(readme_path, name="session_test_file.md")
            logger.info(f"   Uploaded: {node.name}")
            
            # Delete test file
            await client3.delete(node)
            logger.info("   Test file deleted")
            
        finally:
            # Full logout - delete session
            await client3.log_out()
        
        logger.info("   Client 3 logged out (session deleted)")
        
        # =====================================================================
        # Step 4: Verify session deleted
        # =====================================================================
        logger.info("\n[STEP 4] Verify session deleted...")
        
        session = SQLiteSession("test_account", session_path)
        assert not session.exists(), "Session should be deleted after logout"
        session.close()
        
        logger.info("   Session correctly deleted")
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST PASSED - Session persistence works correctly!")
    logger.info("=" * 60)
    
    return True


async def test_backward_compatibility():
    """
    Test backward compatibility with email/password direct login.
    """
    from megapy import MegaClient
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("\n" + "=" * 60)
    logger.info("Backward Compatibility Test")
    logger.info("=" * 60)
    
    # Old style: MegaClient(email, password)
    async with MegaClient(email, password) as mega:
        logger.info("   Logged in with email/password (backward compatible)")
        
        files = await mega.list_files()
        logger.info(f"   Files: {len(files)}")
        
        assert mega.is_logged_in, "Should be logged in"
    
    logger.info("\nOK - Backward compatibility works!")
    return True


async def test_session_with_config():
    """
    Test session with custom configuration.
    """
    from megapy import MegaClient
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("\n" + "=" * 60)
    logger.info("Session with Custom Config Test")
    logger.info("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = MegaClient.create_config(
            timeout=120,
            max_retries=3,
            user_agent="session-test/1.0.0"
        )
        
        client = MegaClient("custom_config", config=config, base_path=Path(tmpdir))
        
        try:
            await client.start(email=email, password=password)
            
            logger.info("   Session created with custom config")
            
            files = await client.list_files()
            logger.info(f"   Files: {len(files)}")
            
        finally:
            await client.log_out()
    
    logger.info("\nOK - Session with config works!")
    return True


def main():
    """Run all session tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test backward compatibility
        result1 = loop.run_until_complete(test_backward_compatibility())
        
        # Test session with config
        result2 = loop.run_until_complete(test_session_with_config())
        
        # Test session persistence
        result3 = loop.run_until_complete(test_session_persistence())
        
        return result1 and result2 and result3
        
    finally:
        loop.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
