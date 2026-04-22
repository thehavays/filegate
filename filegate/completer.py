"""
completer.py — TAB completion engine for FSM.

Provides:
  1. RemoteCompleter   — readline completer for remote paths (interactive mode)
  2. setup_remote_completion(server) — enables remote TAB completion
  3. setup_local_completion()        — enables local filesystem completion
  4. restore_completion()            — restores previous completer
  5. generate_bash_completion()      — returns a bash completion script string
  6. generate_zsh_completion()       — returns a zsh completion script string
  7. install_completion(shell)       — writes + sources the completion script
"""
import os
import readline
import sys
from pathlib import Path
from typing import List, Optional

from .protocols.base import BaseServer, FSEntry


# ─── Remote completer ──────────────────────────────────────────────────────────

class RemoteCompleter:
    """
    readline-compatible completer for remote server paths.

    Caches directory listings to avoid redundant network calls during a single
    completion session (cache is discarded on the next user input).
    """

    def __init__(self, server: BaseServer) -> None:
        self._server     = server
        self._cache: dict[str, List[FSEntry]] = {}
        self._matches: List[str] = []

    # ── Internal ───────────────────────────────────────────────────────────────

    def _get_listing(self, directory: str) -> List[FSEntry]:
        if directory not in self._cache:
            try:
                self._cache[directory] = self._server.listdir(directory)
            except Exception:
                self._cache[directory] = []
        return self._cache[directory]

    def _build_matches(self, text: str) -> List[str]:
        """Return all remote paths that start with *text*."""
        if '/' in text:
            parent = text.rsplit('/', 1)[0] or '/'
            prefix = text.rsplit('/', 1)[1]
        else:
            parent = '/'
            prefix = text

        entries = self._get_listing(parent)
        sep     = '' if parent == '/' else '/'
        results = []
        for entry in entries:
            if entry.name.startswith(prefix):
                full = parent.rstrip('/') + '/' + str(entry.name)
                # Add trailing slash for directories so readline continues
                if entry.is_dir:
                    full += '/'
                results.append(full)
        return results

    # ── readline interface ─────────────────────────────────────────────────────

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            self._matches = self._build_matches(text)
        try:
            return self._matches[state]
        except IndexError:
            return None


# ─── Local path completer ──────────────────────────────────────────────────────

class LocalCompleter:
    """readline completer that expands local filesystem paths."""

    def __init__(self) -> None:
        self._matches: List[str] = []

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            expanded = os.path.expanduser(text)
            if os.path.isdir(expanded):
                candidates = [
                    os.path.join(expanded, name)
                    for name in os.listdir(expanded)
                ]
            else:
                parent  = os.path.dirname(expanded) or '.'
                partial = os.path.basename(expanded)
                try:
                    candidates = [
                        os.path.join(parent, name)
                        for name in os.listdir(parent)
                        if name.startswith(partial)
                    ]
                except OSError:
                    candidates = []
            self._matches = [
                c + ('/' if os.path.isdir(c) else '') for c in sorted(candidates)
            ]
        try:
            return self._matches[state]
        except IndexError:
            return None


# ─── Setup helpers ─────────────────────────────────────────────────────────────

_saved_completer = None
_saved_delims    = None


def setup_remote_completion(server: BaseServer) -> RemoteCompleter:
    """Install remote TAB completion for *server* into readline."""
    global _saved_completer, _saved_delims
    _saved_completer = readline.get_completer()
    _saved_delims    = readline.get_completer_delims()

    completer = RemoteCompleter(server)
    readline.set_completer(completer.complete)
    readline.set_completer_delims(' \t\n')
    readline.parse_and_bind('tab: complete')
    return completer


def setup_local_completion() -> LocalCompleter:
    """Install local filesystem TAB completion into readline."""
    global _saved_completer, _saved_delims
    _saved_completer = readline.get_completer()
    _saved_delims    = readline.get_completer_delims()

    completer = LocalCompleter()
    readline.set_completer(completer.complete)
    readline.set_completer_delims(' \t\n')
    readline.parse_and_bind('tab: complete')
    return completer


def restore_completion() -> None:
    """Restore the completer that was active before setup_*_completion."""
    global _saved_completer, _saved_delims
    if _saved_completer is not None:
        readline.set_completer(_saved_completer)
    if _saved_delims is not None:
        readline.set_completer_delims(_saved_delims)


# ─── Shell completion script generators ───────────────────────────────────────

def generate_bash_completion() -> str:
    return r"""# FileGate bash completion
# Source this file or place it in /etc/bash_completion.d/filegate

# ── Helper: directory-aware local file completion ─────────────────────────────
# Appends '/' to directories so TAB keeps drilling into subdirs without a space.
_filegate_filedir() {
    local cur="$1"
    # Ensure bash handles escaping of spaces/special chars in matches
    compopt -o filenames 2>/dev/null

    if declare -f _filedir > /dev/null 2>&1; then
        # Use bash-completion library if present (handles edge-cases best)
        _filedir
    else
        local -a _matches=()
        while IFS= read -r _f; do
            [[ -d "$_f" ]] && _f="${_f}/"
            _matches+=("$_f")
        done < <(compgen -f -- "$cur")
        COMPREPLY=("${_matches[@]}")
        # Single directory match → no trailing space so user can keep tabbing in
        [[ ${#COMPREPLY[@]} -eq 1 && "${COMPREPLY[0]}" == */ ]] && compopt -o nospace
    fi
}

_filegate_complete() {
    local cur prev words cword
    if declare -f _init_completion > /dev/null 2>&1; then
        # Initialize with colon as a non-breaking character
        _init_completion -n : || return
    else
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    fi

    # Find subcommand and its index
    local subcommand=""
    local sub_idx=0
    for ((i=1; i <= cword; i++)); do
        if [[ " list add remove test pull push copy shell install-completion " == *" ${words[i]} "* ]]; then
            subcommand="${words[i]}"
            sub_idx=$i
            break
        fi
    done
    [[ -z "$subcommand" ]] && subcommand="${words[1]}"
    [[ $sub_idx -eq 0 ]] && sub_idx=1

    # Calculate logical position (merging words joined by backslashes)
    local pos=0
    for ((i=sub_idx+1; i <= cword; i++)); do
        if [[ $i -eq $((sub_idx+1)) || "${words[i-1]}" != *\\ ]]; then
            ((pos++))
        fi
    done

    # Helper: get the full logical word at current cursor position
    _filegate_get_cur() {
        local res="${words[cword]}"
        local i=$((cword-1))
        while [[ $i -ge $((sub_idx+1)) && "${words[i]}" == *\\ ]]; do
            res="${words[i]} ${res}"
            ((i--))
        done
        echo "${res//\\ / }"
    }

    # Helper: get N-th logical argument after subcommand
    _get_logical_arg() {
        local target=$1
        local current=0
        local res=""
        for ((j=sub_idx+1; j < ${#words[@]}; j++)); do
            if [[ $j -eq $((sub_idx+1)) || "${words[j-1]}" != *\\ ]]; then
                ((current++))
                res="${words[j]}"
            else
                res="$res ${words[j]}"
            fi
            if [[ $current -eq $target && "${words[j]}" != *\\ ]]; then
                echo "${res//\\ / }"
                return
            fi
        done
    }

    local cur_logical=$(_filegate_get_cur)
    local commands="list add remove test pull push copy shell install-completion"

    case "$subcommand" in
        copy)
            if [[ "$cur_logical" == *:* ]]; then
                local server="${cur_logical%%:*}"
                local rpath="${cur_logical#*:}"
                local completions
                mapfile -t completions < <("${COMP_WORDS[0]}" _complete remote "$server" "$rpath" 2>/dev/null)
                COMPREPLY=()
                for comp in "${completions[@]}"; do
                    COMPREPLY+=("${server}:${comp}")
                done
                
                # Prevent double-prefixing if bash-completion is present
                if declare -f __ltrim_colon_completions > /dev/null 2>&1; then
                    __ltrim_colon_completions "$cur_logical"
                fi
                compopt -o filenames 2>/dev/null
                [[ ${#COMPREPLY[@]} -eq 1 && "${COMPREPLY[0]}" == */ ]] && compopt -o nospace
            else
                local servers
                servers=$("${COMP_WORDS[0]}" list --names-only 2>/dev/null)
                COMPREPLY=($(compgen -W "$servers" -S ":" -- "$cur"))
                compopt -o nospace
            fi
            ;;

        add)
            case "$prev" in
                --protocol|-p)
                    COMPREPLY=($(compgen -W "sftp ftp ftps smb" -- "$cur"))
                    ;;
                --key|-k)
                    _filegate_filedir "$cur"
                    ;;
                *)
                    COMPREPLY=($(compgen -W "--host --port --user --protocol --key --share --domain" -- "$cur"))
                    ;;
            esac
            ;;

        remove|test|shell)
            COMPREPLY=($(compgen -W "$("${COMP_WORDS[0]}" list --names-only 2>/dev/null)" -- "$cur"))
            ;;

        pull)
            if [[ $pos -eq 1 ]]; then
                COMPREPLY=($(compgen -W "$("${COMP_WORDS[0]}" list --names-only 2>/dev/null)" -- "$cur"))
            elif [[ $pos -eq 2 ]]; then
                local server=$(_get_logical_arg 1)
                mapfile -t COMPREPLY < <("${COMP_WORDS[0]}" _complete remote "$server" "$cur_logical" 2>/dev/null)
                compopt -o filenames 2>/dev/null
                [[ ${#COMPREPLY[@]} -eq 1 && "${COMPREPLY[0]}" == */ ]] && compopt -o nospace
            else
                _filegate_filedir "$cur"
            fi
            ;;

        push)
            if [[ $pos -eq 1 ]]; then
                COMPREPLY=($(compgen -W "$("${COMP_WORDS[0]}" list --names-only 2>/dev/null)" -- "$cur"))
            elif [[ $pos -eq 2 ]]; then
                _filegate_filedir "$cur"
            else
                local server=$(_get_logical_arg 1)
                mapfile -t COMPREPLY < <("${COMP_WORDS[0]}" _complete remote "$server" "$cur_logical" 2>/dev/null)
                compopt -o filenames 2>/dev/null
                [[ ${#COMPREPLY[@]} -eq 1 && "${COMPREPLY[0]}" == */ ]] && compopt -o nospace
            fi
            ;;

        install-completion)
            COMPREPLY=($(compgen -W "--shell" -- "$cur"))
            ;;

        "")
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            ;;

        *)
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            ;;
    esac
}

complete -F _filegate_complete filegate fgate filegate.fgate
"""


def generate_zsh_completion() -> str:
    return r"""#compdef filegate fgate
# FileGate zsh completion

_filegate() {
    local state line
    typeset -A opt_args

    _arguments \
        '1: :_filegate_subcommands' \
        '*:: :->args'

    case $state in
        args)
            case $line[1] in
                add)
                    _arguments \
                        '--host[Server hostname or IP]:host:' \
                        '--port[Port number]:port:' \
                        '--user[Username]:user:' \
                        {-p,--protocol}'[Protocol]:protocol:(sftp ftp ftps smb)' \
                        {-k,--key}'[Path to SSH private key]:key:_files' \
                        '--share[Default SMB share name]:share:' \
                        '--domain[Windows/AD domain for SMB]:domain:'
                    ;;
                remove|test|shell)
                    local servers
                    servers=(${(f)"$($words[1] list --names-only 2>/dev/null)"})
                    _describe 'server' servers
                    ;;
                pull)
                    case $CURRENT in
                        2)
                            local servers
                            servers=(${(f)"$($words[1] list --names-only 2>/dev/null)"})
                            _describe 'server' servers
                            ;;
                        3)
                            local completions
                            completions=(${(f)"$($words[1] _complete remote ${words[2]} ${words[3]} 2>/dev/null)"})
                            _describe 'remote path' completions
                            ;;
                        *)
                            _files
                            ;;
                    esac
                    ;;
                push)
                    case $CURRENT in
                        2)
                            local servers
                            servers=(${(f)"$($words[1] list --names-only 2>/dev/null)"})
                            _describe 'server' servers
                            ;;
                        3)
                            _files
                            ;;
                        *)
                            local completions
                            completions=(${(f)"$($words[1] _complete remote ${words[2]} ${words[4]} 2>/dev/null)"})
                            _describe 'remote path' completions
                            ;;
                    esac
                    ;;
                copy)
                    if [[ "$words[$CURRENT]" == *:* ]]; then
                        local server="${words[$CURRENT]%%:*}"
                        local rpath="${words[$CURRENT]#*:}"
                        local completions
                        completions=(${(f)"$($words[1] _complete remote $server $rpath 2>/dev/null)"})
                        # Prepend server name to matches
                        local -a matches
                        for c in $completions; do matches+=("${server}:$c"); done
                        _describe 'remote path' matches
                    else
                        local servers
                        servers=(${(f)"$($words[1] list --names-only 2>/dev/null)"})
                        # Add colon suffix to server names
                        local -a server_choices
                        for s in $servers; do server_choices+=("$s:"); done
                        _describe 'server' server_choices
                    fi
                    ;;
                install-completion)
                    _arguments '--shell[Shell type]:shell:(bash zsh)'
                    ;;
            esac
            ;;
    esac
}

_filegate_subcommands() {
    local subcommands
    subcommands=(
        'list:List all registered servers and their status'
        'add:Register a new server'
        'remove:Remove a registered server'
        'test:Test connection to a server'
        'pull:Download a file or directory from a server'
        'push:Upload a file or directory to a server'
        'copy:Copy files between servers (remote-to-remote)'
        'shell:Open an interactive shell on a server'
        'install-completion:Install shell TAB completion'
    )
    _describe 'subcommand' subcommands
}

_filegate "$@"
"""


def install_completion(shell: str) -> None:
    """Write the completion script and print sourcing instructions."""
    from rich.console import Console
    from rich.panel   import Panel

    console = Console()
    shell   = shell.lower()

    if shell == 'bash':
        script  = generate_bash_completion()
        dest    = Path.home() / '.bash_completion.d' / 'filegate'
        source_hint = f'source "{dest}"  # add to ~/.bashrc'
    elif shell == 'zsh':
        script  = generate_zsh_completion()
        dest    = Path.home() / '.zsh' / 'completions' / '_filegate'
        source_hint = f'fpath=("{dest.parent}" $fpath)  # add to ~/.zshrc, before compinit'
    else:
        console.print(f'[red]Unknown shell:[/] {shell}. Supported: bash, zsh')
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(script)

    console.print(Panel(
        f'[green]✓[/] Completion script written to [bold]{dest}[/]\n\n'
        f'Add this to your shell config:\n'
        f'[bold cyan]{source_hint}[/]\n\n'
        f'Then restart your shell or run:\n'
        f'[bold cyan]source {dest}[/]',
        title=f'[bold]FileGate {shell.upper()} Completion Installed[/]',
        border_style='green',
    ))
