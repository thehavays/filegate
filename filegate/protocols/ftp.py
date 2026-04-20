"""
protocols/ftp.py — FTP / FTPS backend using Python's built-in ftplib.

Protocol 'ftp'  → plain FTP
Protocol 'ftps' → FTP over TLS (explicit mode)

Both support recursive pull/push.
"""
import ftplib
import io
import os
from pathlib import Path
from typing import List, Optional

from .base import BaseServer, FSEntry, EntryType, ProgressCallback


class FTPServer(BaseServer):

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._ftp: Optional[ftplib.FTP] = None
        self._use_tls: bool = config.get('protocol', 'ftp').lower() == 'ftps'

    @property
    def default_port(self) -> int:
        return 21

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, password: Optional[str] = None) -> None:
        if self._use_tls:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        ftp.connect(self.host, self.port, timeout=10)
        ftp.login(self.user, password or '')

        if self._use_tls:
            ftp.prot_p()  # Switch to encrypted data connection

        self._ftp = ftp
        self._connected = True

    def disconnect(self) -> None:
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                pass
            self._ftp = None
        self._connected = False

    # ── Directory operations ───────────────────────────────────────────────────

    def home(self) -> str:
        return self._ftp.pwd()

    def listdir(self, path: str) -> List[FSEntry]:
        entries: List[FSEntry] = []
        try:
            # Use MLSD if available (RFC 3659), otherwise fall back to LIST
            try:
                facts_list = list(self._ftp.mlsd(path))
                for name, facts in facts_list:
                    if name in ('.', '..'):
                        continue
                    entry_path = path.rstrip('/') + '/' + name
                    ftype = facts.get('type', 'file')
                    if ftype == 'dir':
                        etype = EntryType.DIR
                    elif ftype == 'file':
                        etype = EntryType.FILE
                    else:
                        etype = EntryType.UNKNOWN
                    entries.append(FSEntry(
                        name=str(name),
                        path=path.rstrip('/') + '/' + str(name),
                        type=etype,
                        size=int(facts.get('size', 0)),
                        modified=None  # TODO: parse modified time
                    ))
            except Exception:
                # Fallback to simple nlst()
                for name in self._ftp.nlst(path):
                    if name in ('.', '..'):
                        continue
                    entries.append(FSEntry(
                        name=str(name),
                        path=path.rstrip('/') + '/' + str(name),
                        type=EntryType.UNKNOWN  # Can't know type without stat
                    ))
        except ftplib.all_errors:
            pass

        return sorted(entries, key=lambda e: (e.is_dir is False, e.name))

    def exists(self, path: str) -> bool:
        try:
            self._ftp.cwd(path)
            self._ftp.cwd(self.home())
            return True
        except ftplib.error_perm:
            pass
        try:
            self._ftp.size(path)
            return True
        except ftplib.error_perm:
            return False

    def isdir(self, path: str) -> bool:
        current = self._ftp.pwd()
        try:
            self._ftp.cwd(path)
            self._ftp.cwd(current)
            return True
        except ftplib.error_perm:
            return False

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
            total = self._ftp.size(remote_path) or 0
        except Exception:
            total = 0
        transferred = [0]

        with open(local_path, 'wb') as fh:
            def _write(chunk: bytes) -> None:
                fh.write(chunk)
                transferred[0] += len(chunk)
                if progress:
                    progress(transferred[0], total)

            self._ftp.retrbinary(f'RETR {remote_path}', _write)

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
        transferred = [0]

        with open(local_path, 'rb') as fh:
            def _read_chunk(chunk: bytes) -> None:
                # This is used as the callback form for storbinary
                pass

            # Use storbinary with a progress-aware file wrapper
            class _ProgressFile:
                def __init__(self, fp):
                    self._fp = fp

                def read(self, size=-1):
                    data = self._fp.read(size)
                    transferred[0] += len(data)
                    if progress:
                        progress(transferred[0], total)
                    return data

            self._ftp.storbinary(f'STOR {remote_path}', _ProgressFile(fh))

    def _push_dir(
        self,
        local_dir: Path,
        remote_dir: str,
        progress: Optional[ProgressCallback],
    ) -> None:
        try:
            self._ftp.mkd(remote_dir)
        except ftplib.error_perm:
            pass  # Already exists
        for child in local_dir.iterdir():
            rdst = remote_dir.rstrip('/') + '/' + child.name
            if child.is_dir():
                self._push_dir(child, rdst, progress)
            else:
                self._push_file(str(child), rdst, progress)
