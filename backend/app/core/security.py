"""Password hashing, session tokens and secret encryption. Standard library plus `cryptography` only."""
import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# scrypt parameters (about 16 MB of memory per hash, a few tens of milliseconds)
_N, _R, _P = 2**14, 8, 1
_DUMMY = None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check, so an unknown email is not distinguishable by response time."""
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("not-a-real-password")
    verify_password(password, _DUMMY)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only this hash is stored, so a leaked database does not hand out working sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- encryption for stored API keys ----------

def _fernet() -> Fernet:
    if settings.secret_key is not None and settings.secret_key.get_secret_value().strip():
        raw = settings.secret_key.get_secret_value().strip().encode()
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))
    path: Path = settings.secret_key_path
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(Fernet.generate_key())
    return Fernet(path.read_bytes().strip())


def encrypt_secret(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    """None when the secret key changed or the value is damaged (the user simply re-enters their key)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
