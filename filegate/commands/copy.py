"""
commands/copy.py — Remote-to-remote file transfer logic.
"""
import sys
import getpass
from typing import Tuple

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    DownloadColumn, TransferSpeedColumn, TaskProgressColumn, TimeRemainingColumn
)

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

    # Prompt for passwords if not in keyring and not using SSH keys
    if not src_pw and not src_conf.get('key_file'):
        src_pw = getpass.getpass(f"Password for {src_name} ({src_conf['user']}): ")
    
    # Only prompt for dst password if it's a different server
    if src_name != dst_name:
        if not dst_pw and not dst_conf.get('key_file'):
            dst_pw = getpass.getpass(f"Password for {dst_name} ({dst_conf['user']}): ")

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
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    
                    def _do_copy(s_path: str, d_path: str):
                        if src_server.isdir(s_path):
                            dst_server.mkdir(d_path)
                            for entry in src_server.listdir(s_path):
                                _do_copy(str(entry.path), d_path.rstrip('/') + '/' + str(entry.name))
                        else:
                            # It's a file
                            filename = s_path.split('/')[-1]
                            with src_server.open_file(s_path, 'rb') as f_src, \
                                 dst_server.open_file(d_path, 'wb') as f_dst:
                                
                                total_size = src_server.get_size(s_path)
                                
                                task = progress.add_task(f"Copying {filename}", total=total_size)
                                while True:
                                    chunk = f_src.read(128 * 1024)
                                    if not chunk: break
                                    f_dst.write(chunk)
                                    progress.update(task, advance=len(chunk))
                                progress.remove_task(task)

                    # If destination is a directory, append source name to it
                    final_dst = dst_path
                    if dst_server.isdir(dst_path):
                        src_basename = src_path.rstrip('/').split('/')[-1]
                        final_dst = dst_path.rstrip('/') + '/' + src_basename

                    _do_copy(src_path, final_dst)
                
                console.print("[green]✓[/] Stream copy complete.")

    except Exception as e:
        console.print(f"[red]Error:[/] Transfer failed: {e}")
        sys.exit(1)
