---
name: filegate-assistant
description: Reference and instructions for running and using the filegate CLI application (SSH/SFTP, FTP, SMB client).
---

# FileGate Assistant

This skill provides reference instructions for using the FileGate (`filegate` or `fgate`) application.

## CLI Usage Reference

Antigravity can run the `filegate` or `fgate` command directly to invoke various subcommands. Below is the command reference.

### 1. Registering Servers
To connect to remote file servers, you must first register them:

* **SFTP (SSH) Server**:
  ```bash
  filegate add <name> --host <host> --user <user> --protocol sftp --key <path/to/id_rsa>
  ```
* **FTP / FTPS Server**:
  ```bash
  filegate add <name> --host <host> --user <user> --protocol ftp
  # or
  filegate add <name> --host <host> --user <user> --protocol ftps
  ```
* **SMB (Samba) Server**:
  ```bash
  filegate add <name> --host <host> --user <user> --protocol smb --share <share_name> --domain [domain]
  ```

*Note: The CLI will prompt you for the password securely on `stdin`. Passwords are saved in the system keyring or fall back to local AES-encrypted storage.*

### 2. List Registered Servers & Test Connections
* **List all configured servers**:
  ```bash
  filegate list
  ```
  Shows server configuration and live status.

* **List names only (used for auto-completions)**:
  ```bash
  filegate list --names-only
  ```

* **Test a server connection**:
  ```bash
  filegate test <server_name>
  ```

### 3. Remote-Local Transfers (Pull and Push)
* **Download (Pull) a file or directory**:
  ```bash
  filegate pull <server> [remote_path] [local_path]
  ```
  If `remote_path` or `local_path` are omitted, the CLI will launch an interactive session prompting you for the path with TAB completion.

* **Upload (Push) a file or directory**:
  ```bash
  filegate push <server> [local_path] [remote_path]
  ```

### 4. Remote-to-Remote Copy
* **Copy files between remote servers**:
  ```bash
  filegate copy <src_server>:<src_path> <dst_server>:<dst_path>
  ```
  Performs native server-side copying if within the same server, or streams data via memory to avoid local disk writing.

### 5. Interactive Shell
To browse and manage a server using an interactive shell:
```bash
filegate shell <server_name>
```
*Note: This starts an interactive REPL with standard commands like `ls`, `cd`, `pull`, `push`, `pwd`, etc. with TAB completion.*

### 6. Install Shell TAB Completion
Generates and writes autocompletion script:
```bash
filegate install-completion --shell [bash|zsh]
```
