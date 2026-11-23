"""Password hashing with scrypt from the standard library: a random salt per password, constant-time comparison."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2 ** 14, 8, 1, 32
MIN_LENGTH, MAX_LENGTH = 10, 128


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(digest)))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# Verified against when the email is unknown, so an unknown email and a wrong password take equally long.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
