"""
Debug upload speed - identify bottlenecks.
"""
import asyncio
import aiohttp
import time
import os
import tempfile
from pathlib import Path

# Test file size
TEST_SIZE_MB = 5
TEST_FILE = None


def create_test_file():
    """Create a test file."""
    global TEST_FILE
    TEST_FILE = Path(tempfile.gettempdir()) / "megapy_speed_test.bin"
    print(f"Creating {TEST_SIZE_MB}MB test file: {TEST_FILE}")
    with open(TEST_FILE, 'wb') as f:
        f.write(os.urandom(TEST_SIZE_MB * 1024 * 1024))
    return TEST_FILE


def test_encryption_speed():
    """Test encryption speed alone."""
    from megapy.core.upload.strategies.encryption import MegaEncryptionStrategy
    
    print("\n=== ENCRYPTION SPEED TEST ===")
    
    # Read file
    data = TEST_FILE.read_bytes()
    chunk_sizes = [128 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024]
    
    for chunk_size in chunk_sizes:
        enc = MegaEncryptionStrategy()
        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
        
        start = time.time()
        for i, chunk in enumerate(chunks):
            enc.encrypt_chunk(i, chunk)
        
        # Finalize to ensure MAC completes
        enc.finalize()
        elapsed = time.time() - start
        
        speed_mbps = (len(data) / elapsed) / (1024 * 1024)
        print(f"  Chunk {chunk_size//1024}KB: {elapsed:.3f}s = {speed_mbps:.1f} MB/s")


def test_chunking_strategy():
    """Test chunking configuration."""
    from megapy.core.upload.strategies.chunking import MegaChunkingStrategy
    
    print("\n=== CHUNKING STRATEGY ===")
    
    strategy = MegaChunkingStrategy()
    file_size = TEST_SIZE_MB * 1024 * 1024
    chunks = strategy.calculate_chunks(file_size)
    
    print(f"  File size: {file_size} bytes")
    print(f"  Number of chunks: {len(chunks)}")
    
    for i, (start, end) in enumerate(chunks[:5]):
        print(f"    Chunk {i}: {start}-{end} ({(end-start)//1024}KB)")
    if len(chunks) > 5:
        print(f"    ... and {len(chunks)-5} more chunks")


async def test_http_upload_speed():
    """Test raw HTTP upload speed to MEGA."""
    print("\n=== HTTP UPLOAD SPEED TEST ===")
    
    try:
        from megapy import MegaClient as Mega
        
        mega = Mega()
        await mega.login()  # Anonymous login
        
        # Get upload URL
        file_size = TEST_SIZE_MB * 1024 * 1024
        result = await mega._api.request({'a': 'u', 's': file_size})
        upload_url = result['p']
        
        print(f"  Upload URL obtained")
        
        # Test single chunk upload (no encryption)
        data = os.urandom(1024 * 1024)  # 1MB
        
        # Test 1: New session per request
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{upload_url}/0", data=data) as resp:
                await resp.read()
        elapsed = time.time() - start
        print(f"  1MB upload (new session): {elapsed:.3f}s = {1/elapsed:.1f} MB/s")
        
        # Test 2: Reuse session
        result = await mega._api.request({'a': 'u', 's': file_size})
        upload_url = result['p']
        
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.post(f"{upload_url}/0", data=data) as resp:
                await resp.read()
            elapsed = time.time() - start
            print(f"  1MB upload (reused session): {elapsed:.3f}s = {1/elapsed:.1f} MB/s")
            
            # Test 3: Multiple chunks same session
            result = await mega._api.request({'a': 'u', 's': file_size})
            upload_url = result['p']
            
            start = time.time()
            pos = 0
            for i in range(5):
                async with session.post(f"{upload_url}/{pos}", data=data) as resp:
                    await resp.read()
                pos += len(data)
            elapsed = time.time() - start
            print(f"  5x1MB upload (same session): {elapsed:.3f}s = {5/elapsed:.1f} MB/s")
        
        await mega.close()
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()


async def test_full_upload_with_timing():
    """Test full upload with detailed timing."""
    print("\n=== FULL UPLOAD WITH TIMING ===")
    
    try:
        from megapy import MegaClient as Mega
        from megapy.core.upload.strategies.encryption import MegaEncryptionStrategy
        from megapy.core.upload.strategies.chunking import MegaChunkingStrategy
        
        mega = Mega()
        await mega.login()
        
        file_size = TEST_FILE.stat().st_size
        data = TEST_FILE.read_bytes()
        
        # Get upload URL
        t0 = time.time()
        result = await mega._api.request({'a': 'u', 's': file_size})
        upload_url = result['p']
        t_url = time.time() - t0
        print(f"  Get upload URL: {t_url:.3f}s")
        
        # Calculate chunks
        chunking = MegaChunkingStrategy()
        chunks = chunking.calculate_chunks(file_size)
        print(f"  Chunks: {len(chunks)}")
        
        # Encrypt and upload
        encryption = MegaEncryptionStrategy()
        
        times = {
            'read': 0,
            'encrypt': 0,
            'upload': 0,
        }
        
        async with aiohttp.ClientSession() as session:
            for i, (start, end) in enumerate(chunks):
                # Read
                t0 = time.time()
                chunk_data = data[start:end]
                times['read'] += time.time() - t0
                
                # Encrypt
                t0 = time.time()
                encrypted = encryption.encrypt_chunk(i, chunk_data)
                times['encrypt'] += time.time() - t0
                
                # Upload
                t0 = time.time()
                async with session.post(
                    f"{upload_url}/{start}",
                    data=encrypted,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    await resp.read()
                times['upload'] += time.time() - t0
                
                if (i + 1) % 5 == 0 or i == len(chunks) - 1:
                    print(f"    Chunk {i+1}/{len(chunks)}")
        
        # Finalize
        t0 = time.time()
        file_key = encryption.finalize()
        t_finalize = time.time() - t0
        
        print(f"\n  Timing breakdown:")
        print(f"    Read:     {times['read']:.3f}s")
        print(f"    Encrypt:  {times['encrypt']:.3f}s")
        print(f"    Upload:   {times['upload']:.3f}s ({file_size/times['upload']/1024/1024:.1f} MB/s)")
        print(f"    Finalize: {t_finalize:.3f}s")
        
        total = times['read'] + times['encrypt'] + times['upload'] + t_finalize
        print(f"    TOTAL:    {total:.3f}s ({file_size/total/1024/1024:.1f} MB/s effective)")
        
        await mega.close()
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()


async def test_chunk_uploader_overhead():
    """Test ChunkUploader overhead."""
    print("\n=== CHUNK UPLOADER OVERHEAD ===")
    
    try:
        from megapy import MegaClient as Mega
        from megapy.core.upload.services.chunk_service import ChunkUploader
        
        mega = Mega()
        await mega.login()
        
        file_size = 5 * 1024 * 1024
        result = await mega._api.request({'a': 'u', 's': file_size})
        upload_url = result['p']
        
        uploader = ChunkUploader(upload_url, timeout=120)
        
        data = os.urandom(1024 * 1024)  # 1MB chunks
        
        start = time.time()
        pos = 0
        for i in range(5):
            await uploader.upload_chunk(i, pos, data)
            pos += len(data)
        elapsed = time.time() - start
        
        print(f"  5x1MB via ChunkUploader: {elapsed:.3f}s = {5/elapsed:.1f} MB/s")
        
        await mega.close()
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    create_test_file()
    
    # CPU-bound tests
    test_chunking_strategy()
    test_encryption_speed()
    
    # Network tests
    await test_http_upload_speed()
    await test_chunk_uploader_overhead()
    await test_full_upload_with_timing()
    
    # Cleanup
    if TEST_FILE and TEST_FILE.exists():
        TEST_FILE.unlink()
    
    print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
