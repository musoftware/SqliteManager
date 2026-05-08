"""
utils/helpers.py — Utility helpers.
utils/validators.py — Input validators.
utils/encryption.py — Encrypted settings storage.
"""
from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from typing import Any

from app.logger import get_logger

log = get_logger("utils")


# ── helpers.py ────────────────────────────────────────────────────────────────

def human_size(bytes_: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} PB"


def truncate(text: str, max_len: int = 80) -> str:
    return text if len(text) <= max_len else text[:max_len - 3] + "…"


def safe_json_load(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    except Exception as exc:
        log.warning("JSON load failed (%s): %s", path, exc)
    return default if default is not None else {}


def safe_json_save(path: Path, data: Any) -> None:
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    except Exception as exc:
        log.warning("JSON save failed (%s): %s", path, exc)


# ── validators.py ─────────────────────────────────────────────────────────────

def is_valid_sql_identifier(name: str) -> bool:
    """Check that a name is a safe SQL identifier."""
    import re
    return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))


def validate_db_path(path: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    if not path:
        return False, "Path is empty."
    p = Path(path)
    if not p.exists():
        return False, f"File not found: {path}"
    if not p.is_file():
        return False, f"Not a file: {path}"
    if p.suffix.lower() not in (".db", ".sqlite", ".sqlite3", ".db3", ""):
        return True, ""  # Allow any extension, just warn
    return True, ""


# ── encryption.py ─────────────────────────────────────────────────────────────

class EncryptedStorage:
    """
    Stores connection profiles encrypted with Fernet symmetric encryption.
    Key is derived from a machine-specific secret.
    """

    def __init__(self, path: Path):
        self._path = path
        self._key = self._derive_key()

    def _derive_key(self) -> bytes:
        try:
            from cryptography.fernet import Fernet
            import base64
            # Derive from hostname + username (portable, not truly secret but better than plaintext)
            raw = f"{os.environ.get('COMPUTERNAME', 'default')}:{os.environ.get('USERNAME', 'user')}"
            hashed = hashlib.sha256(raw.encode()).digest()
            return base64.urlsafe_b64encode(hashed)
        except ImportError:
            return b""

    def _fernet(self):
        from cryptography.fernet import Fernet
        return Fernet(self._key)

    def save(self, data: dict) -> None:
        try:
            f = self._fernet()
            encrypted = f.encrypt(json.dumps(data).encode())
            self._path.write_bytes(encrypted)
        except Exception as exc:
            log.warning("Encrypted save failed: %s", exc)
            # Fall back to plain JSON
            self._path.with_suffix(".json").write_text(json.dumps(data, indent=2))

    def load(self) -> dict:
        try:
            if self._path.exists():
                f = self._fernet()
                decrypted = f.decrypt(self._path.read_bytes())
                return json.loads(decrypted)
            # Try plain JSON fallback
            plain = self._path.with_suffix(".json")
            if plain.exists():
                return json.loads(plain.read_text())
        except Exception as exc:
            log.warning("Encrypted load failed: %s", exc)
        return {}
