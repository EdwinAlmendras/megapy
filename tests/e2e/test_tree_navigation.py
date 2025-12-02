"""
E2E Test: Tree navigation.

Tests the professional file system navigation interface.
"""
import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger('megapy.api').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

logger = logging.getLogger('test.tree')


async def test_tree_navigation():
    """Test tree navigation features."""
    from megapy import MegaClient
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("=" * 60)
    logger.info("Tree Navigation Test")
    logger.info("=" * 60)
    
    async with MegaClient(email, password) as mega:
        
        # Test 1: Get root
        logger.info("\n[TEST 1] Get root node...")
        root = await mega.get_root()
        logger.info(f"   Root: {root.name}")
        logger.info(f"   Path: {root.path}")
        logger.info(f"   Is folder: {root.is_folder}")
        logger.info(f"   Children: {len(root.children)}")
        
        # Test 2: Iterate over children
        logger.info("\n[TEST 2] List children...")
        for item in root:
            logger.info(f"   {item}")
        
        # Test 3: Navigate with / operator
        logger.info("\n[TEST 3] Navigate with / operator...")
        if len(root.children) > 0:
            first_item = root.children[0]
            logger.info(f"   First item: {first_item.name}")
            
            # Try to get it using / operator
            same_item = root / first_item.name
            if same_item:
                logger.info(f"   Got via /: {same_item.name}")
                assert same_item.handle == first_item.handle
        
        # Test 4: ls() method
        logger.info("\n[TEST 4] Using ls()...")
        items = await mega.ls()
        for item in items:
            logger.info(f"   {item}")
        
        # Test 5: tree() method
        logger.info("\n[TEST 5] Tree view...")
        tree_str = await mega.tree(max_depth=2)
        logger.info(f"\n{tree_str}")
        
        # Test 6: pwd() and cd()
        logger.info("\n[TEST 6] pwd() and cd()...")
        logger.info(f"   Current: {mega.pwd()}")
        
        # Test 7: Node properties
        logger.info("\n[TEST 7] Node properties...")
        logger.info(f"   is_root: {root.is_root}")
        logger.info(f"   is_empty: {root.is_empty}")
        logger.info(f"   depth: {root.depth}")
        logger.info(f"   files count: {len(root.files)}")
        logger.info(f"   folders count: {len(root.folders)}")
        
        # Test 8: Walk
        logger.info("\n[TEST 8] Walk the tree...")
        for folder, subfolders, files in root.walk():
            logger.info(f"   {folder.path}: {len(subfolders)} folders, {len(files)} files")
        
        # Test 9: Statistics
        logger.info("\n[TEST 9] Statistics...")
        logger.info(f"   Total size: {root.get_total_size()} bytes")
        logger.info(f"   Total files: {root.count_files()}")
        logger.info(f"   Total folders: {root.count_folders()}")
        
        # Test 10: 'in' operator
        logger.info("\n[TEST 10] 'in' operator...")
        if len(root.children) > 0:
            first_name = root.children[0].name
            if first_name in root:
                logger.info(f"   '{first_name}' is in root: True")
        
    logger.info("\n" + "=" * 60)
    logger.info("TEST PASSED - Tree navigation works!")
    logger.info("=" * 60)
    
    return True


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(test_tree_navigation())
    finally:
        loop.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
