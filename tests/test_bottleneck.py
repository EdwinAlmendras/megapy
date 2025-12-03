"""
Simple bottleneck test - measures each step independently.
"""
import asyncio
import aiohttp
import time
import os

# Test config
CHUNK_SIZE = 1024 * 1024  # 1MB
TOTAL_SIZE = 5 * 1024 * 1024  # 5MB

async def test_raw_http_upload():
    """Test raw HTTP upload speed without any megapy code."""
    print("\n=== RAW HTTP UPLOAD TEST ===")
    
    # Create test data
    test_data = os.urandom(CHUNK_SIZE)
    
    # Get upload URL from MEGA (need credentials)
    # For now, test with httpbin or similar
    
    # Test 1: Single session, multiple requests
    print("\n1. Single session, 5 requests of 1MB each:")
    
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Warm up connection
        async with session.get("https://httpbin.org/get") as resp:
            await resp.read()
        
        times = []
        for i in range(5):
            start = time.time()
            async with session.post(
                "https://httpbin.org/post",
                data=test_data[:10000],  # Only 10KB to httpbin
            ) as resp:
                await resp.read()
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.3f}s")
        
        print(f"  Average: {sum(times)/len(times):.3f}s per request")

    # Test 2: New session per request
    print("\n2. New session per request:")
    times = []
    for i in range(5):
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://httpbin.org/post",
                data=test_data[:10000],
            ) as resp:
                await resp.read()
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  Request {i+1}: {elapsed:.3f}s")
    
    print(f"  Average: {sum(times)/len(times):.3f}s per request")


async def test_encryption_speed():
    """Test encryption speed independently."""
    print("\n=== ENCRYPTION SPEED TEST ===")
    
    from megapy.core.upload.strategies.encryption import MegaEncryptionStrategy
    
    test_data = os.urandom(TOTAL_SIZE)
    chunks = [test_data[i:i+CHUNK_SIZE] for i in range(0, len(test_data), CHUNK_SIZE)]
    
    print(f"Test data: {TOTAL_SIZE/1024/1024:.1f}MB in {len(chunks)} chunks")
    
    # Test encryption
    enc = MegaEncryptionStrategy()
    
    start = time.time()
    for i, chunk in enumerate(chunks):
        enc.encrypt_chunk(i, chunk)
    encrypt_time = time.time() - start
    
    print(f"Encryption time: {encrypt_time:.3f}s ({TOTAL_SIZE/encrypt_time/1024/1024:.1f} MB/s)")
    
    # Test finalize (waits for MAC)
    start = time.time()
    enc.finalize()
    finalize_time = time.time() - start
    
    print(f"Finalize time: {finalize_time:.3f}s")
    print(f"Total: {encrypt_time + finalize_time:.3f}s")


async def test_file_reading():
    """Test file reading speed."""
    print("\n=== FILE READING TEST ===")
    
    import tempfile
    from pathlib import Path
    import aiofiles
    
    # Create temp file
    test_file = Path(tempfile.gettempdir()) / "test_read.bin"
    test_file.write_bytes(os.urandom(TOTAL_SIZE))
    
    try:
        # Test sync read
        start = time.time()
        data = test_file.read_bytes()
        sync_time = time.time() - start
        print(f"Sync read: {sync_time:.3f}s ({TOTAL_SIZE/sync_time/1024/1024:.1f} MB/s)")
        
        # Test async read all at once
        start = time.time()
        async with aiofiles.open(test_file, 'rb') as f:
            data = await f.read()
        async_time = time.time() - start
        print(f"Async read (full): {async_time:.3f}s ({TOTAL_SIZE/async_time/1024/1024:.1f} MB/s)")
        
        # Test async read in chunks
        start = time.time()
        async with aiofiles.open(test_file, 'rb') as f:
            for i in range(0, TOTAL_SIZE, CHUNK_SIZE):
                await f.seek(i)
                chunk = await f.read(CHUNK_SIZE)
        chunk_time = time.time() - start
        print(f"Async read (chunks): {chunk_time:.3f}s ({TOTAL_SIZE/chunk_time/1024/1024:.1f} MB/s)")
        
    finally:
        test_file.unlink()


async def test_full_pipeline():
    """Test full pipeline: read -> encrypt -> simulate upload."""
    print("\n=== FULL PIPELINE TEST (no actual upload) ===")
    
    import tempfile
    from pathlib import Path
    import aiofiles
    from megapy.core.upload.strategies.encryption import MegaEncryptionStrategy
    from megapy.core.upload.strategies.chunking import MegaChunkingStrategy
    
    # Create temp file
    test_file = Path(tempfile.gettempdir()) / "test_pipeline.bin"
    test_file.write_bytes(os.urandom(TOTAL_SIZE))
    
    try:
        chunking = MegaChunkingStrategy()
        chunks = chunking.calculate_chunks(TOTAL_SIZE)
        
        print(f"File: {TOTAL_SIZE/1024/1024:.1f}MB, Chunks: {len(chunks)}")
        
        # Pipeline timings
        read_time = 0
        encrypt_time = 0
        
        enc = MegaEncryptionStrategy()
        
        total_start = time.time()
        
        async with aiofiles.open(test_file, 'rb') as f:
            for i, (start, end) in enumerate(chunks):
                # Read
                t0 = time.time()
                await f.seek(start)
                data = await f.read(end - start)
                read_time += time.time() - t0
                
                # Encrypt
                t0 = time.time()
                encrypted = enc.encrypt_chunk(i, data)
                encrypt_time += time.time() - t0
        
        # Finalize
        t0 = time.time()
        enc.finalize()
        finalize_time = time.time() - t0
        
        total_time = time.time() - total_start
        
        print(f"Read:     {read_time:.3f}s ({TOTAL_SIZE/read_time/1024/1024:.1f} MB/s)")
        print(f"Encrypt:  {encrypt_time:.3f}s ({TOTAL_SIZE/encrypt_time/1024/1024:.1f} MB/s)")
        print(f"Finalize: {finalize_time:.3f}s")
        print(f"Total:    {total_time:.3f}s ({TOTAL_SIZE/total_time/1024/1024:.1f} MB/s effective)")
        
    finally:
        test_file.unlink()


async def main():
    await test_file_reading()
    await test_encryption_speed()
    await test_raw_http_upload()
    await test_full_pipeline()
    
    print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
