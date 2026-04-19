"""
commands/copy.py — Remote-to-remote file transfer logic.
"""
import sys
from typing import Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn

import filegate.config as cfg
from filegate.protocols import get_server_instance


def parse_remote_path(path_str: str) -> Tuple[str, str]:
    """Parse 'server:/path' into ('server', '/path')."""
    if ':' not in path_str:
        print(f"[red]Error:[/] Invalid path format '{path_str}'. Use [bold]server:/path[/]")
        sys.exit(1)
    server, path = path_str.split(':', 1)
    return server, path or '/'


def cmd_copy(args):
    console = Console()
    src_name, src_path = parse_remote_path(args.src)
    dst_name, dst_path = parse_remote_path(args.dst)

    src_conf = cfg.get_server(src_name)
    dst_conf = cfg.get_server(dst_name)

    if not src_conf:
        console.print(f"[red]Error:[/] Source server [bold]{src_name}[/] not found.")
        sys.exit(1)
    if not dst_conf:
        console.print(f"[red]Error:[/] Destination server [bold]{dst_name}[/] not found.")
        sys.exit(1)

    src_pw = cfg.get_password(src_name)
    dst_pw = cfg.get_password(dst_name)

    try:
        with get_server_instance(src_conf) as src_server:
            src_server.connect(src_pw)
            
            # Case 1: Intra-server copy (Fastest)
            if src_name == dst_name:
                console.print(f"[blue]Optimizing:[/] Using server-side copy on [bold]{src_name}[/]...")
                src_server.copy_within(src_path, dst_path)
                console.print("[green]✓[/] Copy complete.")
                return

            # Case 2: Inter-server copy (Memory Streaming)
            with get_server_instance(dst_conf) as dst_server:
                dst_server.connect(dst_pw)
                
                console.print(f"[blue]Streaming:[/] [bold]{src_name}[/] → [bold]{dst_name}[/] (via memory)")
                
                # Check if src is a directory (recursive copy not implemented for stream yet)
                if src_server.isdir(src_path):
                    console.print("[yellow]Warning:[/] Recursive cross-server copy via stream is not yet supported.")
                    console.print("Please copy individual files or use pull/push.")
                    return

                with src_server.open_file(src_path, 'rb') as f_src, \
                     dst_server.open_file(dst_path, 'wb') as f_dst:
                    
                    # Try to get size for progress bar
                    try:
                        # This depends on protocol implementation of 'stat' or similar
                        # For now, we'll just stream
                        total_size = 0
                        if hasattr(f_src, 'stat'):
                            total_size = f_src.stat().st_size
                    except:
                        total_size = 0

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task(f"Copying {src_path.split('/')[-1]}", total=total_size)
                        
                        while True:
                            chunk = f_src.read(128 * 1024) # 128KB buffer
                            if not chunk:
                                break
                            f_dst.write(chunk)
                            progress.update(task, advance=len(chunk))
                
                console.print("[green]✓[/] Stream copy complete.")

    except Exception as e:
        console.print(f"[red]Error:[/] Transfer failed: {e}")
        sys.exit(1)
