"""
commands/shell.py — Interactive shell with full navigation and TAB completion.

Commands available inside the shell:
  ls [path]            — list remote directory
  cd <path>            — change remote directory
  pwd                  — print current remote directory
  pull <src> [dst]     — download file/directory
  push <src> [dst]     — upload file/directory
  mkdir <path>         — create remote directory
  help                 — show help
  exit / quit          — disconnect and exit
"""
import getpass
import os
import readline
import sys
from pathlib import Path
from typing import List, Optional

from rich.console  import Console
from rich.progress import (
    BarColumn, FileSizeColumn, Progress, SpinnerColumn,
    TaskProgressColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn,
)
from rich.table    import Table
from rich          import box

import filegate.config as cfg
from filegate.completer import RemoteCompleter
from filegate.protocols import get_server_instance
from filegate.protocols.base import BaseServer, FSEntry, EntryType

console = Console()

SHELL_HELP = """
[bold cyan]FSM Interactive Shell Commands[/]

  [yellow]ls[/] [path]         List remote directory contents
  [yellow]cd[/] <path>         Change remote directory
  [yellow]pwd[/]               Print current remote directory
  [yellow]pull[/] <src> [dst]  Download file or directory from server
  [yellow]push[/] <src> [dst]  Upload local file or directory to server
  [yellow]mkdir[/] <path>      Create a remote directory
  [yellow]help[/]              Show this help message
  [yellow]exit[/] / [yellow]quit[/]       Disconnect and exit

  TAB completes remote paths. Use Ctrl+C to abort a transfer.
"""


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
        transient=True,
    )


def _print_listing(entries: List[FSEntry]) -> None:
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style='bold bright_black',
        padding=(0, 2),
    )
    table.add_column('Type', width=4, justify='center')
    table.add_column('Name', style='white')
    table.add_column('Size', justify='right', style='yellow')

    for entry in entries:
        if entry.is_dir:
            icon = '[cyan]📁[/]'
            name = f'[bold cyan]{entry.display_name}[/]'
        else:
            icon = '[white]📄[/]'
            name = entry.display_name

        size = ''
        if entry.size is not None:
            if entry.size >= 1_073_741_824:
                size = f'{entry.size / 1_073_741_824:.1f} GB'
            elif entry.size >= 1_048_576:
                size = f'{entry.size / 1_048_576:.1f} MB'
            elif entry.size >= 1_024:
                size = f'{entry.size / 1_024:.1f} KB'
            else:
                size = f'{entry.size} B'

        table.add_row(icon, name, size)

    console.print(table)


class ShellCompleter:
    """
    Combined completer for the interactive shell:
      - First word: shell commands
      - Second+ word for pull/push first arg: remote paths  (pull src, push dst)
      - Second word for push: local paths

    *cwd_ref* is a one-element list [cwd_string] kept in sync by the REPL so
    that relative-path TAB completion resolves against the current directory.
    """
    COMMANDS = ['ls', 'cd', 'pwd', 'pull', 'push', 'mkdir', 'help', 'exit', 'quit']

    def __init__(self, server: BaseServer, cwd_ref: list) -> None:
        self._remote  = RemoteCompleter(server)
        self._cwd_ref = cwd_ref   # mutable, updated by the REPL on every cd
        self._matches: List[str] = []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_remote_matches(self, text: str) -> List[str]:
        """
        Complete remote paths.
        - Absolute paths (start with /)  → complete as-is.
        - Relative or empty text         → resolve against current cwd first,
          then strip the cwd prefix from results so completion stays relative.
        """
        if text.startswith('/'):
            return self._remote._build_matches(text)

        # Relative: prefix with cwd for the lookup, strip it from results
        cwd          = self._cwd_ref[0].rstrip('/')
        full_prefix  = cwd + '/' + text
        matches      = self._remote._build_matches(full_prefix)
        strip_prefix = cwd + '/'
        return [
            m[len(strip_prefix):] if m.startswith(strip_prefix) else m
            for m in matches
        ]

    def _local_matches(self, prefix: str) -> List[str]:
        expanded = os.path.expanduser(prefix)
        parent   = os.path.dirname(expanded) or '.'
        partial  = os.path.basename(expanded)
        try:
            names = [n for n in os.listdir(parent) if n.startswith(partial)]
        except OSError:
            names = []
        results = []
        for n in sorted(names):
            full = os.path.join(parent, n)
            results.append(full + ('/' if os.path.isdir(full) else ''))
        return results

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            line_buf = readline.get_line_buffer()
            tokens   = line_buf.lstrip().split()
            cmd      = tokens[0] if tokens else ''
            position = len(tokens) - (1 if line_buf.endswith(' ') else 1)

            if not cmd or (len(tokens) == 1 and not line_buf.endswith(' ')):
                self._matches = [c for c in self.COMMANDS if c.startswith(text)]
            elif cmd in ('ls', 'cd', 'mkdir', 'pull'):
                self._matches = self._build_remote_matches(text)
            elif cmd == 'push':
                if position == 1:
                    self._matches = self._local_matches(text)
                else:
                    self._matches = self._build_remote_matches(text)
            else:
                self._matches = []

        try:
            return self._matches[state]
        except IndexError:
            return None


def cmd_shell(args) -> None:
    name = args.name
    conf = cfg.get_server(name)
    if not conf:
        console.print(f'[red]Server [bold]{name}[/] not found.[/]')
        sys.exit(1)

    password = cfg.get_password(name)
    if not password and not conf.get('key_file'):
        password = getpass.getpass(f'Password for {name}: ')

    server = get_server_instance(conf)
    console.print(f'\nConnecting to [bold]{name}[/] '
                  f'([cyan]{conf["protocol"].upper()}[/] '
                  f'{conf["host"]}:{conf["port"]}) … ', end='')
    try:
        server.connect(password)
    except Exception as exc:
        console.print(f'[red]failed[/]: {exc}')
        sys.exit(1)
    console.print('[green]connected[/]')

    cwd     = server.home()
    cwd_ref = [cwd]   # mutable container so ShellCompleter always reads latest cwd

    # For SMB without a default share, the root is not listable — show a tip
    is_smb_root = (
        conf.get('protocol', '').lower() == 'smb'
        and not conf.get('share')
        and cwd == '/'
    )
    if is_smb_root:
        console.print(
            '[yellow]SMB tip:[/] You are at the server root. '
            'Shares cannot be listed here.\n'
            '  Use [bold cyan]cd <sharename>[/] to navigate into a share '
            f'(e.g. [bold cyan]cd software2[/])\n'
        )
    else:
        console.print(f'Type [bold]help[/] for commands, [bold]exit[/] to quit.\n')

    # Install combined shell completer (receives live cwd reference)
    shell_completer = ShellCompleter(server, cwd_ref)
    readline.set_completer(shell_completer.complete)
    readline.set_completer_delims(' \t\n')
    readline.parse_and_bind('tab: complete')

    # ── REPL ──────────────────────────────────────────────────────────────────
    while True:
        try:
            line = input(f'\n[{name}:{cwd}]> ').strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]Use [bold]exit[/] to quit.[/]')
            continue

        if not line:
            continue

        tokens = line.split(maxsplit=2)
        cmd    = tokens[0].lower()

        # ── pwd ──────────────────────────────────────────────────────────────
        if cmd == 'pwd':
            console.print(f'[cyan]{cwd}[/]')

        # ── ls ───────────────────────────────────────────────────────────────
        elif cmd == 'ls':
            path = tokens[1] if len(tokens) > 1 else cwd
            if not path.startswith('/'):
                path = cwd.rstrip('/') + '/' + path
            try:
                entries = server.listdir(path)
                _print_listing(entries)
            except Exception as exc:
                console.print(f'[red]ls error:[/] {exc}')

        # ── cd ───────────────────────────────────────────────────────────────
        elif cmd == 'cd':
            if len(tokens) < 2:
                cwd = server.home()
            else:
                target = tokens[1]
                if target == '..':
                    cwd = '/'.join(cwd.rstrip('/').split('/')[:-1]) or '/'
                elif target.startswith('/'):
                    cwd = target.rstrip('/') or '/'
                else:
                    cwd = (cwd.rstrip('/') + '/' + target).rstrip('/') or '/'
            cwd_ref[0] = cwd   # keep completer in sync with current directory

        # ── mkdir ─────────────────────────────────────────────────────────────
        elif cmd == 'mkdir':
            if len(tokens) < 2:
                console.print('[yellow]Usage: mkdir <path>[/]')
            else:
                path = tokens[1]
                if not path.startswith('/'):
                    path = cwd.rstrip('/') + '/' + path
                try:
                    server.push.__self__  # just to check it's a real server
                except Exception:
                    pass
                # Use protocol-specific mkdir via push a dummy or direct call
                try:
                    # For SFTP/SMB we can create via their client
                    proto = conf.get('protocol', 'sftp')
                    if proto == 'sftp':
                        server._sftp.mkdir(path)
                    elif proto == 'smb':
                        import smbclient
                        smbclient.mkdir(server._unc(path))
                    else:
                        server._ftp.mkd(path)
                    console.print(f'[green]✓[/] Created [bold]{path}[/]')
                except Exception as exc:
                    console.print(f'[red]mkdir error:[/] {exc}')

        # ── pull ──────────────────────────────────────────────────────────────
        elif cmd == 'pull':
            if len(tokens) < 2:
                console.print('[yellow]Usage: pull <remote_path> [local_dest][/]')
            else:
                remote_src = tokens[1]
                if not remote_src.startswith('/'):
                    remote_src = cwd.rstrip('/') + '/' + remote_src
                local_dst = tokens[2] if len(tokens) > 2 else (
                    './' + remote_src.rstrip('/').split('/')[-1]
                )
                local_dst = str(Path(local_dst).expanduser())

                prog_ctx    = _make_progress()
                task_id_ref = [None]

                def _progress(transferred: int, total: int) -> None:
                    if task_id_ref[0] is None:
                        label = remote_src.split('/')[-1]
                        task_id_ref[0] = prog_ctx.add_task(
                            f'Pulling  {label}', total=total
                        )
                    prog_ctx.update(task_id_ref[0], completed=transferred, total=total)

                try:
                    with prog_ctx:
                        server.pull(remote_src, local_dst, progress=_progress)
                    console.print(f'[green]✓[/] Saved to [bold]{local_dst}[/]')
                except KeyboardInterrupt:
                    console.print('\n[yellow]Transfer cancelled.[/]')
                except Exception as exc:
                    console.print(f'[red]pull error:[/] {exc}')

        # ── push ──────────────────────────────────────────────────────────────
        elif cmd == 'push':
            if len(tokens) < 2:
                console.print('[yellow]Usage: push <local_path> [remote_dest][/]')
            else:
                local_src  = str(Path(tokens[1]).expanduser())
                remote_dst = tokens[2] if len(tokens) > 2 else (
                    cwd.rstrip('/') + '/' + Path(local_src).name
                )
                if not remote_dst.startswith('/'):
                    remote_dst = cwd.rstrip('/') + '/' + remote_dst

                if not Path(local_src).exists():
                    console.print(f'[red]Local path not found:[/] {local_src}')
                    continue

                prog_ctx    = _make_progress()
                task_id_ref = [None]

                def _progress(transferred: int, total: int) -> None:
                    if task_id_ref[0] is None:
                        label = Path(local_src).name
                        task_id_ref[0] = prog_ctx.add_task(
                            f'Pushing  {label}', total=total
                        )
                    prog_ctx.update(task_id_ref[0], completed=transferred, total=total)

                try:
                    with prog_ctx:
                        server.push(local_src, remote_dst, progress=_progress)
                    console.print(f'[green]✓[/] Uploaded to [bold]{name}:{remote_dst}[/]')
                except KeyboardInterrupt:
                    console.print('\n[yellow]Transfer cancelled.[/]')
                except Exception as exc:
                    console.print(f'[red]push error:[/] {exc}')

        # ── help ──────────────────────────────────────────────────────────────
        elif cmd == 'help':
            console.print(SHELL_HELP)

        # ── exit / quit ───────────────────────────────────────────────────────
        elif cmd in ('exit', 'quit'):
            break

        else:
            console.print(
                f'[yellow]Unknown command:[/] [bold]{cmd}[/]  '
                f'(type [bold]help[/] for a list)'
            )

    server.disconnect()
    console.print(f'\n[bright_black]Disconnected from {name}.[/]\n')
