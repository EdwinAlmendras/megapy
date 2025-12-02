"""
Media info - Video/audio metadata
"""
import asyncio
from megapy import MegaClient


async def main():
    async with MegaClient("session") as mega:
        # Optional: Load codec names from MEGA API
        await mega.load_codecs()
        
        root = await mega.get_root()
        
        # Find all media files
        print("Media files:")
        for node in root.walk():
            if not node.has_media_info:
                continue
            
            info = node.media_info
            if not info:
                continue
            
            print(f"\n{node.name}")
            print(f"  Duration: {info.duration_formatted}")
            print(f"  Resolution: {info.resolution}")
            print(f"  FPS: {info.fps}")
            print(f"  Codecs: {info.codec_string}")
            
            # Individual codec names
            print(f"  Container: {info.container_name}")
            print(f"  Video codec: {info.video_codec_name}")
            print(f"  Audio codec: {info.audio_codec_name}")
            
            if info.is_video:
                print("  Type: Video")
            elif info.is_audio:
                print("  Type: Audio")
        
        # Quick check properties
        node = await mega.find("video.mp4")
        if node:
            print(f"\n--- Quick access ---")
            print(f"Duration: {node.duration}s")
            print(f"Resolution: {node.width}x{node.height}")
            print(f"FPS: {node.fps}")
            print(f"Is video: {node.is_video}")
            print(f"Is audio: {node.is_audio}")


if __name__ == "__main__":
    asyncio.run(main())
