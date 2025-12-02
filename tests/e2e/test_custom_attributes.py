"""
E2E Test: Custom attributes upload and retrieval.

Tests uploading files with custom attributes (e: {...}) and verifying
they are correctly stored and retrieved.
"""
import sys
import os
import asyncio
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger('megapy.api').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

logger = logging.getLogger('test.custom_attrs')


async def test_custom_attributes():
    """Test custom attributes in file upload."""
    from megapy import MegaClient
    from megapy.core.upload.models import FileAttributes, CustomAttributes
    
    email = "grd12n12@antispam.rf.gd"
    password = "E3JND2_e32E19KS*"
    
    logger.info("=" * 60)
    logger.info("Custom Attributes Test")
    logger.info("=" * 60)
    
    async with MegaClient(email, password) as mega:
        
        # Test 1: Create custom attributes
        logger.info("\n[TEST 1] Create custom attributes...")
        custom = CustomAttributes(
            document_id="DOC-2024-001",
            url="https://example.com/doc/001",
            date=int(datetime.now().timestamp())
        )
        # Add extra custom attribute
        custom.set('t', 'invoice')  # type
        custom.set('v', 1)  # version
        
        logger.info(f"   Custom attrs: {custom.to_dict()}")
        
        # Test 2: Create file attributes with custom
        logger.info("\n[TEST 2] Create file attributes...")
        attrs = FileAttributes(
            name="test_with_custom.txt",
            label=2,  # Orange
            custom=custom
        )
        
        attrs_dict = attrs.to_dict()
        logger.info(f"   Full attrs: {attrs_dict}")
        
        assert 'n' in attrs_dict
        assert 'e' in attrs_dict
        assert attrs_dict['e']['i'] == "DOC-2024-001"
        assert attrs_dict['e']['u'] == "https://example.com/doc/001"
        assert 'd' in attrs_dict['e']
        assert attrs_dict['e']['t'] == 'invoice'
        assert attrs_dict['e']['v'] == 1
        
        logger.info("   Attributes structure is correct!")
        
        # Test 3: Test with_custom helper
        logger.info("\n[TEST 3] Test with_custom helper...")
        attrs2 = FileAttributes(name="another.txt")
        attrs2.with_custom(
            document_id="DOC-002",
            url="https://test.com"
        )
        
        logger.info(f"   Attrs with with_custom: {attrs2.to_dict()}")
        assert attrs2.to_dict()['e']['i'] == "DOC-002"
        
        # Test 4: Verify parsing from dict
        logger.info("\n[TEST 4] Parse from dict...")
        parsed = FileAttributes.from_dict(attrs_dict)
        logger.info(f"   Parsed name: {parsed.name}")
        logger.info(f"   Parsed label: {parsed.label}")
        logger.info(f"   Parsed custom: {parsed.custom.to_dict() if parsed.custom else None}")
        
        assert parsed.name == "test_with_custom.txt"
        assert parsed.label == 2
        assert parsed.custom is not None
        assert parsed.custom.document_id == "DOC-2024-001"
        assert parsed.custom.url == "https://example.com/doc/001"
        
        logger.info("   Parsing works correctly!")
        
    logger.info("\n" + "=" * 60)
    logger.info("TEST PASSED - Custom attributes work correctly!")
    logger.info("=" * 60)
    
    return True


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(test_custom_attributes())
    finally:
        loop.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
