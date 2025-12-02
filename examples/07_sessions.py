"""
Session management - Login persistence
"""
import asyncio
from megapy import MegaClient


async def main():
    # Method 1: Session file (recommended)
    # First run: prompts for email/password
    # Next runs: auto-login from saved session
    client = MegaClient("my_account")
    await client.start()
    
    root = await client.get_root()
    print(f"Logged in! Files: {len(root.children)}")
    
    await client.close()
    
    
    # Method 2: Context manager with session
    async with MegaClient("my_account") as mega:
        root = await mega.get_root()
        print(f"Files: {len(root.children)}")
    
    
    # Method 3: Direct credentials (no session saved)
    async with MegaClient("email@example.com", "password") as mega:
        root = await mega.get_root()
        print(f"Files: {len(root.children)}")
    
    
    # Method 4: Provide credentials to start()
    client = MegaClient("new_session")
    await client.start(email="email@example.com", password="password")
    await client.close()
    
    
    # Logout and delete session
    async with MegaClient("my_account") as mega:
        await mega.log_out()  # Deletes session file
        print("Logged out!")


if __name__ == "__main__":
    asyncio.run(main())
