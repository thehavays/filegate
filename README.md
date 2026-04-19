# 🗂 FileGate

A powerful command-line tool to **list**, **browse**, **pull**, and **push** files on remote file servers — with full **TAB path completion** on remote paths.

## Features

- 🔌 **Multi-protocol**: SSH/SFTP, FTP, FTPS, SMB2/3
- 🔑 **Secure auth**: SSH key files + password via system keyring (never stored in plaintext)
- 📁 **TAB completion**: remote paths complete in both interactive and inline shell modes
- 🐚 **Interactive shell**: `fgate shell` opens a full REPL with `ls`, `cd`, `pull`, `push`, etc.
- 📊 **Progress bars**: speed, ETA, and file size during all transfers
- 📋 **Server list**: live connection status for all registered servers
- 🔄 **Recursive**: pull/push entire directories

---

## Installation

```bash
pipx install .
```

This installs the `fgate` command globally in an isolated environment.

### 📦 Snap Store (Recommended for Linux)

```bash
sudo snap install filegate
# Grant permission for system keyring access (required for passwords)
sudo snap connect filegate:password-manager-service
```

---

## Quick Start

```bash
# Register servers
fgate add mynas  --host 192.168.1.10 --user admin  --protocol sftp --key ~/.ssh/id_rsa
fgate add backup --host 10.0.0.5     --user ftpuser --protocol ftp
fgate add files  --host 10.0.0.20    --user user    --protocol smb  --share documents

# List all servers with status
fgate list

# Test a connection
fgate test mynas

# Download a file (inline)
fgate pull mynas /home/admin/report.pdf ./report.pdf

# Download interactively with TAB completion
fgate pull mynas
# [mynas] Remote path> /home/admin/doc<TAB>
# /home/admin/documents/
# Local destination [./documents]: ./local_docs/

# Upload a file
fgate push mynas ./local_file.txt /home/admin/uploads/

# Remote-to-remote copy (streaming or server-side)
fgate copy mynas:/home/admin/data.zip backup:/archives/

# Interactive shell
fgate shell mynas
# [mynas:/home/admin]> ls
# [mynas:/home/admin]> cd documents
# [mynas:/home/admin/documents]> pull report.pdf

# Install TAB completion (add to .bashrc to make permanent)
fgate install-completion --shell bash
source ~/.bash_completion.d/fgate
```

---

## Commands

| Command | Description |
|---------|-------------|
| `fgate list` | List registered servers with live status |
| `fgate add <name> --host … --user … --protocol …` | Register a server |
| `fgate remove <name>` | Remove a server |
| `fgate test <name>` | Test connection to a server |
| `fgate pull <server> [remote] [local]` | Download file/directory |
| `fgate push <server> [local] [remote]` | Upload file/directory |
| `fgate shell <name>` | Interactive shell with full TAB completion |
| `fgate install-completion [--shell bash|zsh]` | Install shell completion |

---

## Protocol Reference

| Protocol | Flag | Default Port | Notes |
|----------|------|--------------|-------|
| SSH/SFTP | `--protocol sftp` | 22 | Key or password auth |
| FTP | `--protocol ftp` | 21 | Password auth |
| FTPS | `--protocol ftps` | 21 | FTP over TLS |
| SMB2/3 | `--protocol smb` | 445 | Use `--share` for default share |

---

## TAB Completion Modes

### 1. Interactive mode (built-in, always works)
When `remote_path` is omitted from `pull`/`push`, fgate prompts you interactively with TAB completion enabled on the remote server's filesystem.

### 2. Shell-level completion (one-time setup)
After running `fgate install-completion`, TAB completion works directly in your shell prompt:
```
fgate pull mynas /home/admin/do<TAB>
fgate pull mynas /home/admin/documents/
```

---

## Configuration

Servers are stored in `~/.config/filegate/servers.json`.  
Passwords are stored in your system keyring (GNOME Keyring, KWallet, etc.) — **never in plaintext**.

---

## Shell Support

| Shell | Completion | Notes |
|-------|-----------|-------|
| bash  | ✅ Full | Run `fgate install-completion --shell bash` |
| zsh   | ✅ Full | Run `fgate install-completion --shell zsh` |
