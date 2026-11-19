from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from credsort_common.config import env, is_prod

from .base import AccountingDataProvider
from .bexio import BexioProvider
from .synthetic import SyntheticProvider


def _fernet() -> Fernet:
    key = env("TOKEN_ENCRYPTION_KEY")
    if not key:
        if is_prod():
            raise RuntimeError("TOKEN_ENCRYPTION_KEY is required in prod")
        key = Fernet.generate_key().decode() if not hasattr(_fernet, "_dev") else _fernet._dev  # type: ignore[attr-defined]
        _fernet._dev = key  # type: ignore[attr-defined]
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def provider_for(source_type: str) -> AccountingDataProvider:
    if source_type == "SYNTHETIC":
        return SyntheticProvider()
    if source_type == "BEXIO":
        return BexioProvider(decrypt_token)
    raise ValueError(source_type)
