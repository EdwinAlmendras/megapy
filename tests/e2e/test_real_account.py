"""Real account integration test."""
import sys
import os
import logging

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging - INFO level for cleaner output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Silence verbose loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('RSA_helper').setLevel(logging.WARNING)

logger = logging.getLogger('megapy.test')


def test_real_login_and_list():
    """Test real login and file listing."""
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("=" * 60)
    logger.info("MegaPy Real Account Integration Test")
    logger.info("=" * 60)
    
    try:
        from megapy.core.storage.facade import StorageFacade
        
        # Login
        logger.info(f"Logging in as: {email}")
        storage = StorageFacade()
        result = storage.login(email, password)
        
        logger.info("Login successful!")
        logger.info(f"  User: {result.user_name} (ID: {result.user_id})")
        
        # Load nodes
        logger.info("-" * 40)
        logger.info("Loading file tree...")
        
        root = storage.load_nodes()
        
        if not root:
            logger.error("Failed to load nodes!")
            return False
        
        logger.info(f"Root: {root.name}")
        logger.info(f"Total files/folders: {len(storage._nodes)}")
        
        # Print tree
        logger.info("-" * 40)
        logger.info("File tree:")
        
        def print_tree(node, indent=0):
            prefix = "  " * indent
            if node.is_dir:
                logger.info(f"{prefix}[FOLDER] {node.name}/")
            else:
                logger.info(f"{prefix}[FILE] {node.name} ({node.size} bytes)")
            
            for child in node.get_children():
                print_tree(child, indent + 1)
        
        print_tree(root)
        
        # Verify files
        logger.info("-" * 40)
        files = [n for n in storage._nodes.values() if not n.is_dir]
        logger.info(f"Found {len(files)} files:")
        for f in files:
            logger.info(f"  - {f.name}: {f.size} bytes, key={'OK' if f.key else 'MISSING'}")
        
        logger.info("-" * 40)
        logger.info("TEST PASSED - All operations completed successfully!")
        
        return True
        
    except Exception as e:
        logger.exception(f"TEST FAILED: {e}")
        return False


if __name__ == "__main__":
    success = test_real_login_and_list()
    sys.exit(0 if success else 1)
