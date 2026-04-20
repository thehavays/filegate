"""
main.py — FileGate CLI entry point.

All subcommands:
  fgate list                           List registered servers + live status
  fgate add <name> --host … --user …   Register a new server
  fgate remove <name>                  Remove a server
  fgate test <name>                    Test connection
  fgate pull <server> [remote] [local] Download files (interactive if omitted)
  fgate push <server> [local] [remote] Upload files   (interactive if omitted)
  fgate shell <name>                   Open interactive shell with TAB completion
  fgate install-completion             Write bash/zsh completion script

Hidden internal commands (used by shell completion scripts):
  fgate _complete remote <server> <partial>   Print remote path completions
  fgate list --names-only                     Print server names (one per line)
"""
import argparse
import getpass
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='fgate',
        description='FileGate — connect, browse, pull and push files on remote servers.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest='command', metavar='<command>')
    sub.required = True

    # ── list ──────────────────────────────────────────────────────────────────
    p_list = sub.add_parser('list', help='List registered servers')
    p_list.add_argument(
        '--names-only',
        action='store_true',
        dest='names_only',
        help='Print server names only (for shell completion)',
    )

    # ── add ───────────────────────────────────────────────────────────────────
    p_add = sub.add_parser('add', help='Register a new server')
    p_add.add_argument('name', help='Friendly name for this server')
    p_add.add_argument('--host', required=True, help='Hostname or IP address')
    p_add.add_argument('--port', type=int, default=None, help='Port (uses protocol default)')
    p_add.add_argument('--user', required=True, help='Username')
    p_add.add_argument(
        '--protocol', '-p',
        default='sftp',
        choices=['sftp', 'ftp', 'ftps', 'smb'],
        help='Protocol (default: sftp)',
    )
    p_add.add_argument('--key', '-k', default=None, metavar='KEY_FILE',
                       help='Path to SSH private key file (SFTP only)')
    p_add.add_argument('--share', default=None,
                       help='Default SMB share name (SMB only)')
    p_add.add_argument('--domain', default=None,
                       help='Windows/AD domain for SMB authentication (e.g. ZHCORP)')

    # ── remove ────────────────────────────────────────────────────────────────
    p_rm = sub.add_parser('remove', help='Remove a registered server')
    p_rm.add_argument('name', help='Server name to remove')

    # ── test ──────────────────────────────────────────────────────────────────
    p_test = sub.add_parser('test', help='Test connection to a server')
    p_test.add_argument('name', help='Server name')

    # ── pull ──────────────────────────────────────────────────────────────────
    p_pull = sub.add_parser('pull', help='Download a file or directory from a server')
    p_pull.add_argument('server', help='Server name')
    p_pull.add_argument('remote_path', nargs='?', default=None,
                        help='Remote path (prompted with TAB if omitted)')
    p_pull.add_argument('local_path', nargs='?', default=None,
                        help='Local destination (prompted if omitted)')

    # ── push ──────────────────────────────────────────────────────────────────
    p_push = sub.add_parser('push', help='Upload a file or directory to a server')
    p_push.add_argument('server', help='Server name')
    p_push.add_argument('local_path', nargs='?', default=None,
                        help='Local source path (prompted with TAB if omitted)')
    p_push.add_argument('remote_path', nargs='?', default=None,
                        help='Remote destination (prompted with TAB if omitted)')

    # ── copy ──────────────────────────────────────────────────────────────────
    p_copy = sub.add_parser('copy', help='Copy files between servers (remote-to-remote)')
    p_copy.add_argument('src', help='Source server and path (e.g. server1:/data/file.zip)')
    p_copy.add_argument('dst', help='Destination server and path (e.g. server2:/backup/)')

    # ── shell ─────────────────────────────────────────────────────────────────
    p_shell = sub.add_parser('shell', help='Open an interactive shell on a server')
    p_shell.add_argument('name', help='Server name')

    # ── install-completion ────────────────────────────────────────────────────
    p_comp = sub.add_parser(
        'install-completion',
        help='Install TAB completion script for your shell',
    )
    p_comp.add_argument(
        '--shell',
        default=None,
        choices=['bash', 'zsh'],
        help='Shell type (auto-detected if omitted)',
    )

    # ── _complete (hidden internal) ───────────────────────────────────────────
    p_int = sub.add_parser('_complete', help=argparse.SUPPRESS)
    p_int_sub = p_int.add_subparsers(dest='complete_type')
    p_int_rem = p_int_sub.add_parser('remote')
    p_int_rem.add_argument('server')
    p_int_rem.add_argument('partial', nargs='?', default='/')

    return p


def _detect_shell() -> str:
    """Guess current shell from $SHELL env var."""
    shell_bin = __import__('os').environ.get('SHELL', '')
    if 'zsh' in shell_bin:
        return 'zsh'
    return 'bash'


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    cmd = args.command

    # ── list ──────────────────────────────────────────────────────────────────
    if cmd == 'list':
        from filegate.commands.servers import cmd_list
        cmd_list(args)

    # ── add ───────────────────────────────────────────────────────────────────
    elif cmd == 'add':
        from filegate.commands.servers import cmd_add
        cmd_add(args)

    # ── remove ────────────────────────────────────────────────────────────────
    elif cmd == 'remove':
        from filegate.commands.servers import cmd_remove
        cmd_remove(args)

    # ── test ──────────────────────────────────────────────────────────────────
    elif cmd == 'test':
        from filegate.commands.servers import cmd_test
        cmd_test(args)

    # ── pull ──────────────────────────────────────────────────────────────────
    elif cmd == 'pull':
        from filegate.commands.pull import cmd_pull
        cmd_pull(args)

    # ── push ──────────────────────────────────────────────────────────────────
    elif cmd == 'push':
        from filegate.commands.push import cmd_push
        cmd_push(args)

    # ── copy ──────────────────────────────────────────────────────────────────
    elif cmd == 'copy':
        from filegate.commands.copy import cmd_copy
        cmd_copy(args)

    # ── shell ─────────────────────────────────────────────────────────────────
    elif cmd == 'shell':
        from filegate.commands.shell import cmd_shell
        cmd_shell(args)

    # ── install-completion ────────────────────────────────────────────────────
    elif cmd == 'install-completion':
        from filegate.completer import install_completion
        shell = args.shell or _detect_shell()
        install_completion(shell)

    # ── _complete remote (internal, used by shell scripts) ────────────────────
    elif cmd == '_complete':
        if args.complete_type == 'remote':
            _do_remote_complete(args.server, args.partial)

    else:
        parser.print_help()
        sys.exit(1)


def _do_remote_complete(server_name: str, partial: str) -> None:
    """
    Print remote path completions for *partial* on *server_name*.
    Output is one completion per line (consumed by bash/zsh completion functions).
    """
    import filegate.config as cfg
    from filegate.protocols import get_server_instance
    from filegate.completer import RemoteCompleter

    conf = cfg.get_server(server_name)
    if not conf:
        sys.exit(0)

    password = cfg.get_password(server_name)
    if not password and not conf.get('key_file'):
        # Can't interactively prompt during shell completion.
        # We MUST skip to avoid triggering account lockouts with empty passwords.
        sys.exit(0)

    try:
        server = get_server_instance(conf)
        server.connect(password)
        completer = RemoteCompleter(server)
        matches   = completer._build_matches(partial)
        for m in matches:
            print(m)
        server.disconnect()
    except Exception:
        pass  # Silently fail — completion is best-effort


if __name__ == '__main__':
    main()
