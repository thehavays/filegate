"""
config.py — FileGate server configuration management.

Servers are stored in ~/.config/filegate/servers.json.
Passwords are stored securely via the system keyring (never in plaintext).
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import keyring

CONFIG_DIR = Path.home() / '.config' / 'filegate'
CONFIG_FILE = CONFIG_DIR / 'servers.json'
KEYRING_SERVICE = 'filegate'

PROTOCOL_DEFAULTS = {
    'sftp':  {'port': 22},
    'ftp':   {'port': 21},
    'ftps':  {'port': 21},
    'smb':   {'port': 445},
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_raw() -> dict:
    _ensure_config_dir()
    if not CONFIG_FILE.exists():
        return {'servers': {}}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _save_raw(data: dict) -> None:
    _ensure_config_dir()
    with open(CONFIG_FILE, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)


# ─── Public API ────────────────────────────────────────────────────────────────

def get_servers() -> Dict[str, dict]:
    """Return all registered servers as {name: config_dict}."""
    return _load_raw().get('servers', {})


def get_server(name: str) -> Optional[dict]:
    """Return a single server config or None if not found."""
    return get_servers().get(name)


def server_names() -> List[str]:
    """Return sorted list of registered server names."""
    return sorted(get_servers().keys())


def add_server(name: str, server_config: dict) -> None:
    """Register a new server (overwrite if already exists)."""
    data = _load_raw()
    data.setdefault('servers', {})[name] = server_config
    _save_raw(data)


def remove_server(name: str) -> bool:
    """Remove a server; returns True if it existed."""
    data = _load_raw()
    if name in data.get('servers', {}):
        del data['servers'][name]
        _save_raw(data)
        # Remove password from keyring (best-effort)
        try:
            keyring.delete_password(KEYRING_SERVICE, name)
        except Exception:
            pass
        return True
    return False


def get_password(name: str) -> Optional[str]:
    """Retrieve stored password for a server from the system keyring."""
    return keyring.get_password(KEYRING_SERVICE, name)


def set_password(name: str, password: str) -> None:
    """Store a password for a server in the system keyring."""
    keyring.set_password(KEYRING_SERVICE, name, password)


def default_port(protocol: str) -> int:
    """Return the default port for a given protocol name."""
    return PROTOCOL_DEFAULTS.get(protocol, {}).get('port', 22)
