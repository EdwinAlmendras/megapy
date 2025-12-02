"""Grid preview generator using ffmpeg."""
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Optional, Tuple


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data.get('format', {}).get('duration', 0))
    except Exception:
        return 0


def generate_grid_preview(
    video_path: Path,
    cell_size: int = 360,
    output_quality: int = 85
) -> Optional[bytes]:
    """
    Generate a grid preview image from video frames.
    
    - 4x4 grid (16 frames) for videos >= 60 seconds
    - 3x3 grid (9 frames) for videos < 60 seconds
    
    Args:
        video_path: Path to video file
        cell_size: Size of each cell in pixels (default 360)
        output_quality: JPEG quality (default 85)
        
    Returns:
        JPEG image bytes or None on error
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return None
    
    # Determine grid size based on duration
    if duration >= 60:
        cols, rows = 4, 4
        total_frames = 16
    else:
        cols, rows = 3, 3
        total_frames = 9
    
    # Calculate interval between frames
    interval = duration / (total_frames + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_path = tmpdir / "grid.jpg"
        
        # Build ffmpeg filter for grid
        # Extract frames at regular intervals and create mosaic
        select_filter = "+".join([
            f"eq(n,{int((i + 1) * interval * 30)})"  # Assuming ~30fps
            for i in range(total_frames)
        ])
        
        # Use select filter with tile
        filter_complex = (
            f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{interval})',"
            f"scale={cell_size}:{cell_size}:force_original_aspect_ratio=decrease,"
            f"pad={cell_size}:{cell_size}:(ow-iw)/2:(oh-ih)/2:black,"
            f"tile={cols}x{rows}"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-vf', filter_complex,
            '-frames:v', '1',
            '-q:v', str(int((100 - output_quality) / 10 + 1)),
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if output_path.exists():
                return output_path.read_bytes()
        except Exception:
            pass
    
    return None


def generate_grid_thumbnail(
    video_path: Path,
    cell_size: int = 80,  # 80*3=240 for 3x3, 60*4=240 for 4x4
) -> Optional[bytes]:
    """
    Generate a thumbnail from grid (240x240).
    
    Args:
        video_path: Path to video file
        cell_size: Size per cell to achieve 240x240 total
        
    Returns:
        JPEG thumbnail bytes or None
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return None
    
    if duration >= 60:
        cols, rows = 4, 4
        cell_size = 60  # 60*4 = 240
    else:
        cols, rows = 3, 3
        cell_size = 80  # 80*3 = 240
    
    total_frames = cols * rows
    interval = duration / (total_frames + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_path = tmpdir / "thumb.jpg"
        
        filter_complex = (
            f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{interval})',"
            f"scale={cell_size}:{cell_size}:force_original_aspect_ratio=decrease,"
            f"pad={cell_size}:{cell_size}:(ow-iw)/2:(oh-ih)/2:black,"
            f"tile={cols}x{rows}"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-vf', filter_complex,
            '-frames:v', '1',
            '-q:v', '2',
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if output_path.exists():
                return output_path.read_bytes()
        except Exception:
            pass
    
    return None
