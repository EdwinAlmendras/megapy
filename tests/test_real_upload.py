"""
Real upload test with detailed timing.
"""
import asyncio
import time
import os
import tempfile
from pathlib import Path


async def test_upload():
    """Test real upload with timing."""
    from megapy import MegaClient
    
    print("=== REAL UPLOAD TEST ===\n")
    
    # Create 5MB test file
    test_file = Path(tempfile.gettempdir()) / "megapy_test_upload.bin"
    size_mb = 5
    print(f"Creating {size_mb}MB test file...")
    test_file.write_bytes(os.urandom(size_mb * 1024 * 1024))
    
    try:
        print("Connecting to MEGA...")
        t0 = time.time()
        
        # Use kmp.session from ecosystem folder
        session_file = Path(r"C:\Users\ed2\Documents\drkproy\ecosystem\kmp.session")
        client = MegaClient(str(session_file))
        
        await client.start()
        connect_time = time.time() - t0
        print(f"Connected in {connect_time:.2f}s")
        
        # Upload with progress tracking
        print(f"\nUploading {test_file.name}...")
        
        upload_start = time.time()
        last_update = time.time()
        last_bytes = 0
        
        def progress_callback(p):
            nonlocal last_update, last_bytes
            now = time.time()
            elapsed = now - last_update
            
            if elapsed >= 0.5:  # Update every 0.5s
                bytes_diff = p.uploaded_bytes - last_bytes
                speed = bytes_diff / elapsed / 1024  # KB/s
                pct = p.percentage
                print(f"  {pct:.1f}% - {p.uploaded_bytes//1024}KB - {speed:.1f} KB/s")
                last_update = now
                last_bytes = p.uploaded_bytes
        
        result = await client.upload(
            test_file,
            progress_callback=progress_callback,
            auto_thumb=False  # Skip thumbnail processing
        )
        
        upload_time = time.time() - upload_start
        file_size = test_file.stat().st_size
        speed = file_size / upload_time / 1024  # KB/s
        
        print(f"\nUpload complete!")
        print(f"  Time: {upload_time:.2f}s")
        print(f"  Speed: {speed:.1f} KB/s ({speed/1024:.2f} MB/s)")
        print(f"  File: {result.name} ({result.handle})")
        
        # Cleanup - delete the uploaded file
        print("\nCleaning up...")
        await client.delete(result)
        
        await client.close()
        
    finally:
        test_file.unlink()
    
    print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(test_upload())
