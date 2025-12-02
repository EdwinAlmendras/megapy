"""MEGA CLI - Main commands."""
import asyncio
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

app = typer.Typer(
    name="mega",
    help="MEGA cloud storage CLI",
    add_completion=False
)
console = Console()

# Session path: ~/.config/mega/session.session
def get_session_path() -> Path:
    config_dir = Path.home() / ".config" / "mega"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "session"


def run_async(coro):
    """Run async function."""
    return asyncio.run(coro)


@app.command()
def login(
    email: str = typer.Option(None, "--email", "-e", help="MEGA email"),
    password: str = typer.Option(None, "--password", "-p", help="MEGA password"),
):
    """Login to MEGA and save session."""
    from megapy import MegaClient
    
    if not email:
        email = typer.prompt("Email")
    if not password:
        password = typer.prompt("Password", hide_input=True)
    
    async def do_login():
        session_path = get_session_path()
        client = MegaClient(str(session_path))
        
        try:
            await client.connect()
            await client.login(email, password)
            console.print(f"[green]Logged in as {email}[/green]")
            console.print(f"Session saved to: {session_path}.session")
        except Exception as e:
            console.print(f"[red]Login failed: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await client.close()
    
    run_async(do_login())


@app.command()
def logout():
    """Logout and delete session."""
    session_file = get_session_path().with_suffix(".session")
    if session_file.exists():
        session_file.unlink()
        console.print("[green]Logged out successfully[/green]")
    else:
        console.print("[yellow]No active session[/yellow]")


@app.command()
def whoami():
    """Show current logged in user."""
    from megapy.core.session import SQLiteSession
    
    session_file = get_session_path().with_suffix(".session")
    if not session_file.exists():
        console.print("[red]Not logged in. Run 'mega login' first.[/red]")
        raise typer.Exit(1)
    
    session = SQLiteSession(str(get_session_path()))
    data = session.load()
    session.close()
    
    if data:
        console.print(f"Email: {data.email}")
        console.print(f"User ID: {data.user_id}")
        console.print(f"Session: {session_file}")
    else:
        console.print("[red]Session corrupted. Run 'mega login' again.[/red]")


@app.command()
def ls(
    path: str = typer.Argument("/", help="Path to list"),
    long: bool = typer.Option(False, "-l", "--long", help="Long format with details"),
):
    """List files and folders."""
    from megapy import MegaClient
    
    async def list_files():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            root = await mega.get_root()
            
            # Navigate to path
            if path != "/":
                parts = path.strip("/").split("/")
                node = root
                for part in parts:
                    node = node / part
                    if not node:
                        console.print(f"[red]Path not found: {path}[/red]")
                        raise typer.Exit(1)
            else:
                node = root
            
            if long:
                table = Table()
                table.add_column("Type", style="cyan")
                table.add_column("Size", justify="right")
                table.add_column("Name")
                table.add_column("Handle", style="dim")
                
                for child in node:
                    type_str = "D" if child.is_folder else "F"
                    size_str = "-" if child.is_folder else f"{child.size:,}"
                    table.add_row(type_str, size_str, child.name, child.handle)
                
                console.print(table)
            else:
                for child in node:
                    if child.is_folder:
                        console.print(f"[blue]{child.name}/[/blue]")
                    else:
                        console.print(child.name)
    
    run_async(list_files())


@app.command()
def upload(
    file_path: Path = typer.Argument(..., help="Local file to upload", exists=True),
    dest: str = typer.Option("/", "--dest", "-d", help="Destination folder path"),
    name: str = typer.Option(None, "--name", "-n", help="Custom file name"),
    label: int = typer.Option(0, "--label", "-l", help="Color label (0-7)"),
    no_thumb: bool = typer.Option(False, "--no-thumb", help="Disable auto thumbnail"),
    thumbnail: Path = typer.Option(None, "--thumbnail", "-t", help="Custom thumbnail image"),
    preview: Path = typer.Option(None, "--preview", "-p", help="Custom preview image"),
    preview_grid: bool = typer.Option(False, "--preview-grid", "-g", help="Generate grid preview for videos"),
    doc_id: str = typer.Option(None, "--doc-id", help="Custom document ID attribute"),
    url: str = typer.Option(None, "--url", help="Custom URL attribute"),
):
    """Upload a file to MEGA."""
    from megapy import MegaClient
    from megapy.core.upload.models import UploadProgress
    
    async def do_upload():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            root = await mega.get_root()
            
            # Find destination folder
            dest_handle = None
            if dest != "/":
                parts = dest.strip("/").split("/")
                node = root
                for part in parts:
                    node = node / part
                    if not node:
                        console.print(f"[red]Destination not found: {dest}[/red]")
                        raise typer.Exit(1)
                dest_handle = node.handle
            
            # Build custom attributes
            custom = {}
            if doc_id:
                custom['i'] = doc_id
            if url:
                custom['u'] = url
            
            # Handle grid preview
            thumb_path = thumbnail
            preview_path = preview
            
            if preview_grid and file_path.suffix.lower() in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
                from .grid import generate_grid_preview, generate_grid_thumbnail
                import tempfile
                
                console.print("[cyan]Generating grid preview...[/cyan]")
                
                grid_preview = generate_grid_preview(file_path)
                grid_thumb = generate_grid_thumbnail(file_path)
                
                if grid_preview:
                    # Save to temp files
                    tmp_preview = Path(tempfile.gettempdir()) / "mega_grid_preview.jpg"
                    tmp_preview.write_bytes(grid_preview)
                    preview_path = tmp_preview
                    console.print("[green]Grid preview generated[/green]")
                
                if grid_thumb:
                    tmp_thumb = Path(tempfile.gettempdir()) / "mega_grid_thumb.jpg"
                    tmp_thumb.write_bytes(grid_thumb)
                    thumb_path = tmp_thumb
                    console.print("[green]Grid thumbnail generated[/green]")
            
            # Progress callback
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Uploading {file_path.name}", total=100)
                
                def on_progress(p: UploadProgress):
                    progress.update(task, completed=p.percentage)
                
                result = await mega.upload(
                    file_path,
                    dest_folder=dest_handle,
                    name=name,
                    progress_callback=on_progress,
                    custom=custom if custom else None,
                    label=label,
                    auto_thumb=not no_thumb,
                    thumbnail=thumb_path,
                    preview=preview_path,
                )
            
            console.print(f"[green]Uploaded:[/green] {result.name}")
            console.print(f"Handle: {result.handle}")
            console.print(f"Size: {result.size:,} bytes")
    
    run_async(do_upload())


@app.command()
def download(
    remote_path: str = typer.Argument(..., help="Remote file path or handle"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Download a file from MEGA."""
    from megapy import MegaClient
    
    async def do_download():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            root = await mega.get_root()
            
            # Try to find by path or handle
            node = None
            if remote_path.startswith("/"):
                parts = remote_path.strip("/").split("/")
                node = root
                for part in parts:
                    node = node / part
                    if not node:
                        break
            else:
                # Try as handle
                node = mega.get_node(remote_path)
            
            if not node:
                # Try find by name
                node = await mega.find(remote_path)
            
            if not node:
                console.print(f"[red]File not found: {remote_path}[/red]")
                raise typer.Exit(1)
            
            if node.is_folder:
                console.print("[red]Cannot download folder (yet)[/red]")
                raise typer.Exit(1)
            
            output_path = output or Path(node.name)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Downloading {node.name}", total=node.size)
                
                def on_progress(downloaded, total):
                    progress.update(task, completed=downloaded)
                
                await node.download(output_path, progress_callback=on_progress)
            
            console.print(f"[green]Downloaded:[/green] {output_path}")
    
    run_async(do_download())


@app.command()
def mkdir(
    path: str = typer.Argument(..., help="Folder path to create"),
):
    """Create a folder."""
    from megapy import MegaClient
    
    async def do_mkdir():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            parts = path.strip("/").split("/")
            name = parts[-1]
            parent_path = "/".join(parts[:-1])
            
            root = await mega.get_root()
            parent = root
            
            if parent_path:
                for part in parent_path.split("/"):
                    parent = parent / part
                    if not parent:
                        console.print(f"[red]Parent path not found: {parent_path}[/red]")
                        raise typer.Exit(1)
            
            folder = await mega.create_folder(name, parent.handle)
            console.print(f"[green]Created folder:[/green] {path}")
    
    run_async(do_mkdir())


@app.command()
def rm(
    path: str = typer.Argument(..., help="File or folder to delete"),
    force: bool = typer.Option(False, "-f", "--force", help="Force delete without confirmation"),
):
    """Delete a file or folder."""
    from megapy import MegaClient
    
    async def do_rm():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            root = await mega.get_root()
            
            # Find node
            node = None
            if path.startswith("/"):
                parts = path.strip("/").split("/")
                node = root
                for part in parts:
                    node = node / part
            else:
                node = await mega.find(path)
            
            if not node:
                console.print(f"[red]Not found: {path}[/red]")
                raise typer.Exit(1)
            
            if not force:
                confirm = typer.confirm(f"Delete '{node.name}'?")
                if not confirm:
                    raise typer.Abort()
            
            await node.delete()
            console.print(f"[green]Deleted:[/green] {node.name}")
    
    run_async(do_rm())


@app.command()
def mv(
    source: str = typer.Argument(..., help="Source file/folder"),
    dest: str = typer.Argument(..., help="Destination folder"),
):
    """Move a file or folder."""
    from megapy import MegaClient
    
    async def do_mv():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            root = await mega.get_root()
            
            # Find source
            src_node = None
            if source.startswith("/"):
                parts = source.strip("/").split("/")
                src_node = root
                for part in parts:
                    src_node = src_node / part
            else:
                src_node = await mega.find(source)
            
            if not src_node:
                console.print(f"[red]Source not found: {source}[/red]")
                raise typer.Exit(1)
            
            # Find destination
            dest_node = root
            if dest != "/":
                parts = dest.strip("/").split("/")
                for part in parts:
                    dest_node = dest_node / part
                    if not dest_node:
                        console.print(f"[red]Destination not found: {dest}[/red]")
                        raise typer.Exit(1)
            
            await src_node.move(dest_node)
            console.print(f"[green]Moved:[/green] {src_node.name} -> {dest}")
    
    run_async(do_mv())


@app.command()
def info(
    path: str = typer.Argument(..., help="File path or handle"),
):
    """Show file information."""
    from megapy import MegaClient
    
    async def show_info():
        session_path = get_session_path()
        if not session_path.with_suffix(".session").exists():
            console.print("[red]Not logged in. Run 'mega login' first.[/red]")
            raise typer.Exit(1)
        
        async with MegaClient(str(session_path)) as mega:
            await mega.load_codecs()
            root = await mega.get_root()
            
            # Find node
            node = None
            if path.startswith("/"):
                parts = path.strip("/").split("/")
                node = root
                for part in parts:
                    node = node / part
            else:
                node = mega.get_node(path) or await mega.find(path)
            
            if not node:
                console.print(f"[red]Not found: {path}[/red]")
                raise typer.Exit(1)
            
            console.print(f"[bold]Name:[/bold] {node.name}")
            console.print(f"[bold]Handle:[/bold] {node.handle}")
            console.print(f"[bold]Type:[/bold] {'Folder' if node.is_folder else 'File'}")
            
            if node.is_file:
                console.print(f"[bold]Size:[/bold] {node.size:,} bytes")
                console.print(f"[bold]Has thumbnail:[/bold] {node.has_thumbnail}")
                console.print(f"[bold]Has preview:[/bold] {node.has_preview}")
                
                if node.has_media_info:
                    info = node.media_info
                    if info:
                        console.print(f"[bold]Duration:[/bold] {info.duration_formatted}")
                        console.print(f"[bold]Resolution:[/bold] {info.resolution}")
                        console.print(f"[bold]FPS:[/bold] {info.fps}")
                        console.print(f"[bold]Codecs:[/bold] {info.codec_string}")
    
    run_async(show_info())


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
