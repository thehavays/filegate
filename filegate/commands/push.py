"""
commands/push.py — Upload files / directories to a remote server.

Interactive mode  (no local_path given):
  - Prompts for local source with local filesystem TAB completion
  - Prompts for remote destination with remote TAB completion

Inline mode (all args provided):
  - Executes directly without prompts
"""
import getpass
import sys
from pathlib import Path

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


def cmd_push(args) -> None:
    name = args.server
    conf = cfg.get_server(name)
    if not conf:
        console.print(f'[red]Server [bold]{name}[/] not found.[/]')
        sys.exit(1)

    # ── Get local source (before connecting — no network needed) ───────────────
    local_path: str = getattr(args, 'local_path', None) or ''

    if not local_path:
        setup_local_completion()
        try:
            local_path = input('Local source path> ').strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]Aborted.[/]')
            return
        finally:
            restore_completion()

    if not local_path:
        console.print('[yellow]No local path specified.[/]')
        return

    local_path = str(Path(local_path).expanduser())
    if not Path(local_path).exists():
        console.print(f'[red]Local path not found:[/] {local_path}')
        sys.exit(1)

    # ── Connect ────────────────────────────────────────────────────────────────
    server = _connect(name, conf)

    # ── Get remote destination ─────────────────────────────────────────────────
    remote_path: str = getattr(args, 'remote_path', None) or ''

    if not remote_path:
        home        = server.home()
        default_dst = home.rstrip('/') + '/' + Path(local_path).name
        setup_remote_completion(server)
        try:
            remote_path = input(
                f'\n[{name}] Remote destination [{default_dst}]: '
            ).strip() or default_dst
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]Aborted.[/]')
            server.disconnect()
            return
        finally:
            restore_completion()

    # If the remote destination ends with '/', treat it as a directory and
    # place the local item inside it  (same behaviour as cp / scp / rsync).
    # e.g.  fsm push server file.txt /remote/dir/
    #        → uploads to  /remote/dir/file.txt
    if remote_path.endswith('/'):
        remote_path = remote_path.rstrip('/') + '/' + Path(local_path).name

    # ── Transfer ───────────────────────────────────────────────────────────────
    console.print()

    with _make_progress() as progress:
        def _do_push(l_path: str, r_path: str):
            lp = Path(l_path)
            if lp.is_dir():
                # Ensure remote directory exists
                try:
                    server.mkdir(r_path)
                except: pass # It might already exist
                
                for entry in lp.iterdir():
                    sub_l = str(entry)
                    sub_r = r_path.rstrip('/') + '/' + str(entry.name)
                    _do_push(sub_l, sub_r)
            else:
                # It's a file
                fname = lp.name
                total_size = lp.stat().st_size
                task_id = progress.add_task(f"Pushing {fname}", total=total_size)
                
                def cb(transferred, total):
                    progress.update(task_id, completed=transferred, total=total)
                
                server.push(l_path, r_path, progress=cb)

        try:
            _do_push(local_path, remote_path)
            console.print(f'[green]✓[/] Uploaded to [bold]{name}:{remote_path}[/]')
        except Exception as exc:
            console.print(f'[red]✗ Push failed:[/] {exc}')
            sys.exit(1)
        finally:
            server.disconnect()
