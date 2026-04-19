"""
protocols/base.py — Abstract base class for all server protocol backends.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class EntryType(Enum):
    FILE = 'file'
    DIR  = 'dir'
    LINK = 'link'
    UNKNOWN = 'unknown'


@dataclass
class DirEntry:
    name: str
    path: str          # Full absolute path on the remote server
    type: EntryType
    size: Optional[int] = None       # bytes, None if unknown
    modified: Optional[float] = None  # Unix timestamp, None if unknown

    @property
    def is_dir(self) -> bool:
        return self.type == EntryType.DIR

    @property
    def display_name(self) -> str:
        return self.name + '/' if self.is_dir else self.name


ProgressCallback = Callable[[int, int], None]   # (transferred_bytes, total_bytes)


class BaseServer(ABC):
    """
    Abstract base for all FSM server backends.

    Subclasses must implement the abstract methods below.
    All paths are POSIX-style regardless of the underlying protocol.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.name: str = config.get('name', '')
        self.host: str = config['host']
        self.port: int = int(config.get('port', self.default_port))
        self.user: str = config.get('user', '')
        self._connected: bool = False

    @property
    def default_port(self) -> int:
        return 22

    @property
    def protocol_name(self) -> str:
        return self.config.get('protocol', 'unknown').upper()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self, password: Optional[str] = None) -> None:
        """Open the connection to the remote server."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""

    def is_connected(self) -> bool:
        return self._connected

    # ── Directory operations ───────────────────────────────────────────────────

    @abstractmethod
    def listdir(self, path: str) -> List[DirEntry]:
        """List the contents of a remote directory."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return True if the remote path exists."""

    @abstractmethod
    def isdir(self, path: str) -> bool:
        """Return True if the remote path is a directory."""

    @abstractmethod
    def home(self) -> str:
        """Return the home / default starting directory on the server."""

    # ── Transfer operations ────────────────────────────────────────────────────

    @abstractmethod
    def pull(
        self,
        remote_path: str,
        local_path: str,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Download *remote_path* to *local_path*.
        If remote_path is a directory, download it recursively.
        """

    @abstractmethod
    def push(
        self,
        local_path: str,
        remote_path: str,
        progress: Optional[ProgressCallback] = None,
    ) -> None:
    """
    Upload *local_path* to *remote_path*.
    If local_path is a directory, upload it recursively.
    """

    @abstractmethod
    def open_file(self, path: str, mode: str = 'rb'):
        """Return a file-like object for the remote file."""

    def copy_within(self, src: str, dst: str, progress: Optional[ProgressCallback] = None) -> None:
        """
        Copy a file to a new location on the same server.
        Default implementation uses streaming if not overridden by protocol optimization.
        """
        with self.open_file(src, 'rb') as f_src:
            # We don't know the size easily without stat, so progress might be limited
            with self.open_file(dst, 'wb') as f_dst:
                while True:
                    chunk = f_src.read(64 * 1024)
                    if not chunk:
                        break
                    f_dst.write(chunk)

    # ── Context manager ────────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __repr__(self) -> str:
        status = 'connected' if self._connected else 'disconnected'
        return f'<{self.protocol_name} {self.name}@{self.host}:{self.port} [{status}]>'
