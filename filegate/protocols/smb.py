"""
protocols/smb.py — SMB2/3 backend using smbprotocol / smbclient.

Remote paths use the format:  /share_name/path/to/file
An optional 'share' key in config sets a default share so paths become: /path/to/file

Internally, paths are converted to UNC format: //host/share/path
"""
import os
from pathlib import Path, PurePosixPath
from typing import List, Optional

import smbclient
import smbclient.shutil as smb_shutil
from smbprotocol.exceptions import SMBException

from .base import BaseServer, DirEntry, EntryType, ProgressCallback

_CHUNK = 64 * 1024  # 64 KB copy buffer


class SMBServer(BaseServer):

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._default_share: str = config.get('share', '')
        self._domain: str = config.get('domain', '')

    @property
    def default_port(self) -> int:
        return 445

    # ── Path helpers ───────────────────────────────────────────────────────────

    def _unc(self, path: str) -> str:
        """Convert a user-facing path to a UNC path for smbclient."""
        parts = PurePosixPath(path).parts          # e.g. ('/', 'software2', 'dir', 'file')
        stripped = [p for p in parts if p != '/']  # drop leading '/'

        if self._default_share:
            share = self._default_share
            # Strip the leading share component if it matches _default_share
            # to avoid doubling: /software2 → //host/software2/software2
            if stripped and stripped[0].lower() == share.lower():
                sub_parts = stripped[1:]
            else:
                sub_parts = stripped
            sub = '/'.join(sub_parts)
        elif stripped:
            share = stripped[0]
            sub   = '/'.join(stripped[1:])
        else:
            share = ''
            sub   = ''

        base = f'//{self.host}/{share}'
        return (base + '/' + sub).rstrip('/') if sub else base

    def _user_path(self, unc: str) -> str:
        """Convert a UNC path back to a user-facing /share/path string."""
        # unc = //host/share/rest
        without_host = unc.replace(f'//{self.host}', '', 1)
        return without_host or '/'

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, password: Optional[str] = None) -> None:
        # smbprotocol uses NTLM format: DOMAIN\username
        ntlm_user = f'{self._domain}\\{self.user}' if self._domain else self.user

        smbclient.register_session(
            self.host,
            username=ntlm_user,
            password=password or '',
            port=self.port,
        )
        self._connected = True

    def disconnect(self) -> None:
        try:
            smbclient.reset_connection_cache()
        except Exception:
            pass
        self._connected = False

    # ── Directory operations ───────────────────────────────────────────────────

    def home(self) -> str:
        """Return the top-level share path."""
        if self._default_share:
            return f'/{self._default_share}'
        return '/'

    def listdir(self, path: str) -> List[DirEntry]:
        unc = self._unc(path)

        # Guard: //host with no share is not browsable via smbclient
        if unc.rstrip('/') == f'//{self.host}':
            raise ValueError(
                "You are at the SMB server root — shares cannot be listed here.\n"
                "  Use  [bold]cd <sharename>[/]  to enter a share  "
                "(e.g. [bold cyan]cd software2[/])"
            )

        entries: List[DirEntry] = []
        try:
            for entry in smbclient.scandir(unc):
                entry_unc  = unc.rstrip('/') + '/' + entry.name
                entry_path = self._user_path(entry_unc)
                is_dir = entry.is_dir()
                is_link = entry.is_symlink()
                etype = EntryType.DIR if is_dir else (EntryType.LINK if is_link else EntryType.FILE)
                try:
                    st   = entry.stat()
                    size = st.st_size
                    mtime = st.st_mtime
                except Exception:
                    size = mtime = None

                entries.append(DirEntry(
                    name=entry.name,
                    path=entry_path,
                    type=etype,
                    size=size,
                    modified=mtime,
                ))
        except SMBException:
            pass

        return sorted(entries, key=lambda e: (e.is_dir is False, e.name))

    def exists(self, path: str) -> bool:
        try:
            smbclient.stat(self._unc(path))
            return True
        except (SMBException, Exception):
            return False

    def isdir(self, path: str) -> bool:
        try:
            st = smbclient.stat(self._unc(path))
            import stat as _stat
            return _stat.S_ISDIR(st.st_mode)
        except Exception:
            return False

    def open_file(self, path: str, mode: str = 'rb'):
        return smbclient.open_file(self._unc(path), mode=mode)

    def copy_within(self, src: str, dst: str, progress: Optional[ProgressCallback] = None) -> None:
        """Optimized server-side copy using SMB2/3 FSCTL_SRV_COPYCHUNK."""
        src_unc = self._unc(src)
        dst_unc = self._unc(dst)
        # smbclient.shutil.copyfile uses server-side copy if available
        smb_shutil.copyfile(src_unc, dst_unc)

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
        unc = self._unc(remote_path)
        try:
            total = smbclient.stat(unc).st_size or 0
        except Exception:
            total = 0
        transferred = 0

        with smbclient.open_file(unc, mode='rb') as src, open(local_path, 'wb') as dst:
            while True:
                chunk = src.read(_CHUNK)
                if not chunk:
                    break
                dst.write(chunk)
                transferred += len(chunk)
                if progress:
                    progress(transferred, total)

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
        unc   = self._unc(remote_path)
        total = os.path.getsize(local_path)
        transferred = 0

        with open(local_path, 'rb') as src, smbclient.open_file(unc, mode='wb') as dst:
            while True:
                chunk = src.read(_CHUNK)
                if not chunk:
                    break
                dst.write(chunk)
                transferred += len(chunk)
                if progress:
                    progress(transferred, total)

    def _push_dir(
        self,
        local_dir: Path,
        remote_dir: str,
        progress: Optional[ProgressCallback],
    ) -> None:
        unc = self._unc(remote_dir)
        try:
            smbclient.mkdir(unc)
        except Exception:
            pass
        for child in local_dir.iterdir():
            rdst = remote_dir.rstrip('/') + '/' + child.name
            if child.is_dir():
                self._push_dir(child, rdst, progress)
            else:
                self._push_file(str(child), rdst, progress)
