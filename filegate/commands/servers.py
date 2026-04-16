"""
commands/servers.py — list, add, remove, test commands.
"""
import getpass
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from rich.console import Console
from rich.table   import Table
from rich import box

import filegate.config as cfg
from filegate.protocols import get_server_instance, SUPPORTED_PROTOCOLS

console = Console()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_host(host: str) -> str:
    """Strip UNC prefix and trailing slashes so we get a bare hostname/IP."""
    # e.g. '//server/share/' -> 'server'
    h = host.lstrip('/')
    h = h.split('/')[0]   # take only the first path component
    return h.strip()


def _ping(host: str, port: int, timeout: float = 2.0) -> bool:
    """Quick TCP connect to test if host:port is reachable."""
    hostname = _clean_host(host)
    try:
        with socket.create_connection((hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_status(name: str, conf: dict) -> str:
    """Return '● online' or '✗ offline' for a server."""
    ok = _ping(conf['host'], int(conf.get('port', cfg.default_port(conf.get('protocol', 'sftp')))))
    return '[green]● online[/]' if ok else '[red]✗ offline[/]'


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(args) -> None:
    """List all registered servers with status."""
    servers = cfg.get_servers()

    # names-only mode for shell completion scripts
    if getattr(args, 'names_only', False):
        for name in sorted(servers):
            print(name)
        return

    if not servers:
        console.print('[yellow]No servers registered.[/]  Use [bold]fsm add[/] to add one.')
        return

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style='bold cyan',
        border_style='bright_black',
        title='[bold]Registered File Servers[/]',
    )
    table.add_column('Name',     style='bold white',  min_width=12)
    table.add_column('Host',     style='cyan',         min_width=16)
    table.add_column('Protocol', style='magenta',      min_width=8)
    table.add_column('Port',     style='yellow',       min_width=6, justify='right')
    table.add_column('User',     style='white',        min_width=10)
    table.add_column('Domain',   style='bright_blue',  min_width=8)
    table.add_column('Auth',     style='bright_black', min_width=10)
    table.add_column('Status',   min_width=12)

    # Check statuses concurrently
    statuses: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_check_status, n, c): n for n, c in servers.items()}
        for fut in as_completed(futures):
            statuses[futures[fut]] = fut.result()

    for name in sorted(servers):
        conf = servers[name]
        auth = '🔑 key' if conf.get('key_file') else '🔒 password'
        table.add_row(
            name,
            conf.get('host', '—'),
            conf.get('protocol', '?').upper(),
            str(conf.get('port', '—')),
            conf.get('user', '—'),
            conf.get('domain', '—'),
            auth,
            statuses.get(name, '…'),
        )

    console.print()
    console.print(table)
    console.print()


def cmd_add(args) -> None:
    """Register a new server interactively."""
    name     = args.name
    protocol = args.protocol.lower()

    if protocol not in SUPPORTED_PROTOCOLS:
        console.print(f'[red]Unknown protocol:[/] {protocol}. '
                      f'Supported: {", ".join(SUPPORTED_PROTOCOLS)}')
        sys.exit(1)

    existing = cfg.get_server(name)
    if existing:
        console.print(f'[yellow]Server [bold]{name}[/] already exists.[/]  '
                      f'Run [bold]fsm remove {name}[/] first to replace it.')
        sys.exit(1)

    host_clean = _clean_host(args.host)   # strip any accidental UNC prefix

    server_cfg: dict = {
        'name':     name,
        'host':     host_clean,
        'port':     args.port or cfg.default_port(protocol),
        'user':     args.user,
        'protocol': protocol,
    }

    if getattr(args, 'domain', None):
        server_cfg['domain'] = args.domain.upper()

    if args.key:
        server_cfg['key_file'] = args.key
        # Optionally store key passphrase
        passphrase = getpass.getpass(
            f'SSH key passphrase for {args.key} '
            '(leave blank if none): '
        )
        if passphrase:
            cfg.set_password(name, passphrase)
    else:
        password = getpass.getpass(f'Password for {args.user}@{host_clean} '
                                   '(leave blank to prompt each time): ')
        if password:
            cfg.set_password(name, password)

    if args.share:
        server_cfg['share'] = args.share

    cfg.add_server(name, server_cfg)
    domain_hint = f' domain=[bold]{server_cfg["domain"]}[/]' if 'domain' in server_cfg else ''
    console.print(f'[green]✓[/] Server [bold]{name}[/] added '
                  f'([cyan]{protocol.upper()}[/] {args.user}@{host_clean}{domain_hint})')


def cmd_remove(args) -> None:
    """Remove a registered server."""
    name = args.name
    if not cfg.get_server(name):
        console.print(f'[red]Server [bold]{name}[/] not found.[/]')
        sys.exit(1)

    # Confirm
    confirm = input(f'Remove server "{name}"? [y/N] ').strip().lower()
    if confirm != 'y':
        console.print('[yellow]Aborted.[/]')
        return

    cfg.remove_server(name)
    console.print(f'[green]✓[/] Server [bold]{name}[/] removed.')


def cmd_test(args) -> None:
    """Test connection to a server."""
    name = args.name
    conf = cfg.get_server(name)
    if not conf:
        console.print(f'[red]Server [bold]{name}[/] not found.[/]')
        sys.exit(1)

    password = cfg.get_password(name)
    if not password and not conf.get('key_file'):
        # prompt for password for this test (including SMB)
        password = getpass.getpass(f'Password for {name}: ')

    server = get_server_instance(conf)
    console.print(f'Connecting to [bold]{name}[/] '
                  f'([cyan]{conf["protocol"].upper()}[/] '
                  f'{conf["host"]}:{conf["port"]}) …')
    try:
        server.connect(password)
        home = server.home()
        server.disconnect()
        console.print(f'[green]✓ Connection successful![/]  Home: [bold]{home}[/]')
    except Exception as exc:
        console.print(f'[red]✗ Connection failed:[/] {exc}')
        sys.exit(1)
