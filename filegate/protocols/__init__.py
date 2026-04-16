"""
protocols/__init__.py — Protocol factory.

Use get_server_instance(config) to create the right backend for a server config.
"""
from typing import Dict, Type

from .base import BaseServer
from .sftp import SFTPServer
from .ftp  import FTPServer
from .smb  import SMBServer

_REGISTRY: Dict[str, Type[BaseServer]] = {
    'sftp': SFTPServer,
    'ftp':  FTPServer,
    'ftps': FTPServer,
    'smb':  SMBServer,
}

SUPPORTED_PROTOCOLS = list(_REGISTRY.keys())


def get_server_instance(config: dict) -> BaseServer:
    """
    Instantiate the correct server backend from a server config dict.

    Raises ValueError for unknown protocols.
    """
    protocol = config.get('protocol', 'sftp').lower()
    cls = _REGISTRY.get(protocol)
    if cls is None:
        raise ValueError(
            f"Unknown protocol '{protocol}'. "
            f"Supported: {', '.join(SUPPORTED_PROTOCOLS)}"
        )
    return cls(config)
