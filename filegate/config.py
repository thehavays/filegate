"""
config.py — FileGate server configuration management.

Servers are stored in ~/.config/filegate/servers.json.
Passwords are stored securely via the system keyring (never in plaintext).
"""
import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring

CONFIG_DIR = Path.home() / '.config' / 'filegate'
CONFIG_FILE = CONFIG_DIR / 'servers.json'
KEYRING_SERVICE = 'filegate'

# File-based fallback paths for password storage
KEY_FILE = CONFIG_DIR / 'key'
SECRETS_FILE = CONFIG_DIR / 'secrets.enc'

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
        # Remove password from keyring and local file (best-effort)
        try:
            keyring.delete_password(KEYRING_SERVICE, name)
        except Exception:
            pass
        _delete_file_password(name)
        return True
    return False


def _get_encryption_key() -> bytes:
    _ensure_config_dir()
    # 1. Check environment variable first
    env_password = os.environ.get("FILEGATE_MASTER_PASSWORD")
    if env_password:
        salt = b"filegate_salt_constant"  # Static salt for reproducibility
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(env_password.encode()))
    
    # 2. Check local keyfile
    if KEY_FILE.exists():
        try:
            return KEY_FILE.read_bytes()
        except Exception:
            pass
    
    # 3. Generate new keyfile
    key = Fernet.generate_key()
    try:
        if KEY_FILE.exists():
            KEY_FILE.unlink()
        KEY_FILE.touch()
        os.chmod(KEY_FILE, 0o600)
        KEY_FILE.write_bytes(key)
    except Exception:
        pass
    return key


def _get_file_password(name: str) -> Optional[str]:
    if not SECRETS_FILE.exists():
        return None
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        with open(SECRETS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        encrypted_val = data.get(name)
        if encrypted_val:
            return fernet.decrypt(encrypted_val.encode('utf-8')).decode('utf-8')
    except Exception:
        pass
    return None


def _set_file_password(name: str, password: str) -> None:
    data = {}
    _ensure_config_dir()
    if SECRETS_FILE.exists():
        try:
            with open(SECRETS_FILE, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception:
            pass
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        data[name] = fernet.encrypt(password.encode('utf-8')).decode('utf-8')
        
        # Ensure secure permissions on secrets file
        if not SECRETS_FILE.exists():
            SECRETS_FILE.touch()
            os.chmod(SECRETS_FILE, 0o600)
        with open(SECRETS_FILE, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def _delete_file_password(name: str) -> None:
    if not SECRETS_FILE.exists():
        return
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if name in data:
            del data[name]
            with open(SECRETS_FILE, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
    except Exception:
        pass


def get_password(name: str) -> Optional[str]:
    """Retrieve stored password for a server, falling back to local encrypted file if keyring fails."""
    try:
        backend = keyring.get_keyring()
        if backend and 'fail.Keyring' in str(type(backend)):
            return _get_file_password(name)
    except Exception:
        pass

    try:
        pwd = keyring.get_password(KEYRING_SERVICE, name)
        if pwd is not None:
            return pwd
    except Exception:
        pass

    return _get_file_password(name)


def set_password(name: str, password: str) -> None:
    """Store a password for a server in the system keyring, falling back to local encrypted file if keyring fails."""
    use_file = False
    try:
        backend = keyring.get_keyring()
        if backend and 'fail.Keyring' in str(type(backend)):
            use_file = True
    except Exception:
        use_file = True

    if not use_file:
        try:
            keyring.set_password(KEYRING_SERVICE, name, password)
            _delete_file_password(name)
            return
        except Exception:
            pass

    _set_file_password(name, password)


def default_port(protocol: str) -> int:
    """Return the default port for a given protocol name."""
    return PROTOCOL_DEFAULTS.get(protocol, {}).get('port', 22)
