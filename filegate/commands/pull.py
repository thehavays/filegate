"""
commands/pull.py — Download files / directories from a remote server.

Interactive mode  (no remote_path given):
  - Connects to the server
  - Prompts for remote path with full remote TAB completion
  - Prompts for local destination with local filesystem completion

Inline mode (all args provided):
  - Executes directly without prompts
"""
import getpass
import sys
from pathlib import Path
from typing import Optional

from rich.console  import Console
from rich.progress import (
    BarColumn, FileSizeColumn, Progress, SpinnerColumn,
    TaskProgressColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn,
)

import filegate.config as cfg
from filegate.completer import (
    restore_completion,
    setup_local_completion,
    setup_remote_completion,
)
from filegate.protocols import get_server_instance

console = Console()


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn('[bold cyan]{task.description}[/]'),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        FileSizeColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


def _connect(name: str, conf: dict):
    password = cfg.get_password(name)
    if not password and not conf.get('key_file'):
        password = getpass.getpass(f'Password for {name}: ')

    server = get_server_instance(conf)
    console.print(f'Connecting to [bold]{name}[/] '
                  f'([cyan]{conf["protocol"].upper()}[/] '
                  f'{conf["host"]}:{conf["port"]}) … ', end='')
    try:
        server.connect(password)
        console.print('[green]connected[/]')
    except Exception as exc:
        console.print(f'[red]failed[/]: {exc}')
        sys.exit(1)
    return server


def cmd_pull(args) -> None:
    name = args.server
    conf = cfg.get_server(name)
    if not conf:
        console.print(f'[red]Server [bold]{name}[/] not found.[/]')
        sys.exit(1)

    server = _connect(name, conf)

    # ── Get remote path ────────────────────────────────────────────────────────
    remote_path: str = getattr(args, 'remote_path', None) or ''

    if not remote_path:
        # Interactive: enable remote TAB completion and prompt
        setup_remote_completion(server)
        try:
            remote_path = input(f'\n[{name}] Remote path> ').strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]Aborted.[/]')
            server.disconnect()
            return
        finally:
            restore_completion()

    if not remote_path:
        console.print('[yellow]No path specified.[/]')
        server.disconnect()
        return

    # ── Get local destination ──────────────────────────────────────────────────
    local_path: str = getattr(args, 'local_path', None) or ''

    if not local_path:
        # Default to cwd / basename of remote
        default = './' + remote_path.rstrip('/').split('/')[-1]
        setup_local_completion()
        try:
            local_path = input(f'Local destination [{default}]: ').strip() or default
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]Aborted.[/]')
            server.disconnect()
            return
        finally:
            restore_completion()

    local_path = str(Path(local_path).expanduser())

    # If the local destination is an existing directory, place the remote
    # item *inside* it (same behaviour as cp / scp / rsync).
    # e.g.  filegate pull server /remote/file.txt ./mydir/
    #        → saves to  ./mydir/file.txt
    local_p = Path(local_path)
    if local_p.is_dir():
        remote_name = remote_path.rstrip('/').split('/')[-1]
        local_path  = str(local_p / remote_name)

    # ── Transfer ───────────────────────────────────────────────────────────────
    console.print()

    with _make_progress() as progress:
        def _do_pull(r_path: str, l_path: str):
            if server.isdir(r_path):
                # Create local directory
                Path(l_path).mkdir(parents=True, exist_ok=True)
                
                entries = server.listdir(r_path)
                for entry in entries:
                    # entry is now always an FSEntry object
                    name = str(entry.name)
                    
                    # Skip hidden items like . and ..
                    if name in ('.', '..'): continue
                    
                    sub_r = str(r_path).rstrip('/') + '/' + name
                    sub_l = str(Path(l_path) / name)
                    _do_pull(sub_r, sub_l)
            else:
                # It's a file
                fname = Path(l_path).name
                total_size = server.get_size(r_path)
                task_id = progress.add_task(f"Pulling {fname}", total=total_size)
                
                def cb(transferred, total):
                    progress.update(task_id, completed=transferred, total=total)
                
                # Ensure parent local dir exists
                Path(l_path).parent.mkdir(parents=True, exist_ok=True)
                server.pull(r_path, l_path, progress=cb)

        try:
            _do_pull(remote_path, local_path)
            console.print(f'[green]✓[/] Saved to [bold]{local_path}[/]')
        except Exception as exc:
            console.print(f'[red]✗ Pull failed:[/] {exc}')
            sys.exit(1)
        finally:
            server.disconnect()
