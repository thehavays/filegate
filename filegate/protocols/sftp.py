"""
protocols/sftp.py — SSH/SFTP backend using paramiko.

Supports:
  - SSH key authentication  (key_file in config, passphrase via keyring)
  - Password authentication  (password via keyring or prompts)
  - Recursive pull/push
"""
import os
import stat
from pathlib import Path
from typing import List, Optional

import paramiko

from .base import BaseServer, DirEntry, EntryType, ProgressCallback


class SFTPServer(BaseServer):

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    @property
    def default_port(self) -> int:
        return 22

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, password: Optional[str] = None) -> None:
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict = {
            'hostname': self.host,
            'port':     self.port,
            'username': self.user,
            'timeout':  10,
        }

        key_file = self.config.get('key_file')
        if key_file:
            key_path = os.path.expanduser(key_file)
            # Try to load the key; pass any stored passphrase
            try:
                pkey = paramiko.RSAKey.from_private_key_file(key_path, password=password)
            except paramiko.ssh_exception.PasswordRequiredException:
                raise ValueError(
                    f"SSH key '{key_file}' requires a passphrase. "
                    "Add it with: fsm add --pass-type passphrase"
                )
            connect_kwargs['pkey'] = pkey
        elif password:
            connect_kwargs['password'] = password
        else:
            # Try agent / default keys
            connect_kwargs['look_for_keys'] = True
            connect_kwargs['allow_agent'] = True

        self._ssh.connect(**connect_kwargs)
        self._sftp = self._ssh.open_sftp()
        self._connected = True

    def disconnect(self) -> None:
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._ssh:
            self._ssh.close()
            self._ssh = None
        self._connected = False

    # ── Directory operations ───────────────────────────────────────────────────

    def home(self) -> str:
        return self._sftp.normalize('.')

    def listdir(self, path: str) -> List[DirEntry]:
        entries: List[DirEntry] = []
        try:
            for attr in self._sftp.listdir_attr(path):
                entry_path = path.rstrip('/') + '/' + attr.filename
                mode = attr.st_mode or 0
                if stat.S_ISDIR(mode):
                    etype = EntryType.DIR
                elif stat.S_ISLNK(mode):
                    etype = EntryType.LINK
                elif stat.S_ISREG(mode):
                    etype = EntryType.FILE
                else:
                    etype = EntryType.UNKNOWN
                entries.append(
                    DirEntry(
                        name=attr.filename,
                        path=entry_path,
                        type=etype,
                        size=attr.st_size,
                        modified=attr.st_mtime,
                    )
                )
        except IOError:
            pass
        return sorted(entries, key=lambda e: (e.is_dir is False, e.name))

    def exists(self, path: str) -> bool:
        try:
            self._sftp.stat(path)
            return True
        except IOError:
            return False

    def isdir(self, path: str) -> bool:
        try:
            st = self._sftp.stat(path)
            return stat.S_ISDIR(st.st_mode)
        except IOError:
            return False

    def open_file(self, path: str, mode: str = 'rb'):
        return self._sftp.open(path, mode)

    def copy_within(self, src: str, dst: str, progress: Optional[ProgressCallback] = None) -> None:
        """Optimized server-side copy using SSH 'cp'."""
        import shlex
        # Try native copy first (fastest)
        cmd = f"cp -r {shlex.quote(src)} {shlex.quote(dst)}"
        stdin, stdout, stderr = self._ssh.exec_command(cmd)
        err = stderr.read().decode().strip()
        if err:
            # Fallback to base streaming if cp fails (e.g. restricted shell)
            super().copy_within(src, dst, progress)

    # ── Transfer ───────────────────────────────────────────────────────────────

    def pull(
        self,
        remote_path: str,
        local_path: str,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        local = Path(local_path)
        if self.isdir(remote_path):
            local.mkdir(parents=True, exist_ok=True)
            self._pull_dir(remote_path, local, progress)
        else:
            local.parent.mkdir(parents=True, exist_ok=True)
            self._pull_file(remote_path, str(local), progress)

    def _pull_file(
        self,
        remote_path: str,
        local_path: str,
        progress: Optional[ProgressCallback],
    ) -> None:
        try:
            total = self._sftp.stat(remote_path).st_size or 0
        except Exception:
            total = 0
        transferred = [0]

        def _cb(sent: int, total_: int) -> None:
            transferred[0] = sent
            if progress:
                progress(sent, total_)

        self._sftp.get(remote_path, local_path, callback=_cb)

    def _pull_dir(
        self,
        remote_dir: str,
        local_dir: Path,
        progress: Optional[ProgressCallback],
    ) -> None:
        for entry in self.listdir(remote_dir):
            dst = local_dir / entry.name
            if entry.is_dir:
                dst.mkdir(parents=True, exist_ok=True)
                self._pull_dir(entry.path, dst, progress)
            else:
                self._pull_file(entry.path, str(dst), progress)

    def push(
        self,
        local_path: str,
        remote_path: str,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        local = Path(local_path)
        if local.is_dir():
            self._push_dir(local, remote_path, progress)
        else:
            self._push_file(str(local), remote_path, progress)

    def _push_file(
        self,
        local_path: str,
        remote_path: str,
        progress: Optional[ProgressCallback],
    ) -> None:
        total = os.path.getsize(local_path)

        def _cb(sent: int, total_: int) -> None:
            if progress:
                progress(sent, total_)

        self._sftp.put(local_path, remote_path, callback=_cb)

    def _push_dir(
        self,
        local_dir: Path,
        remote_dir: str,
        progress: Optional[ProgressCallback],
    ) -> None:
        try:
            self._sftp.mkdir(remote_dir)
        except IOError:
            pass  # already exists
        for child in local_dir.iterdir():
            rdst = remote_dir.rstrip('/') + '/' + child.name
            if child.is_dir():
                self._push_dir(child, rdst, progress)
            else:
                self._push_file(str(child), rdst, progress)
