"""Verification of the *user* token obtained by the BFF (ADR-0016): Keycloak in production/Compose, a dev signer otherwise."""
from __future__ import annotations

from dataclasses import dataclass

import jwt

from credsort_common.config import env, is_prod
from credsort_common.errors import Unauthorized
from credsort_common.security import JwksCache, RS256Verifier


@dataclass(frozen=True)
class UserIdentity:
    sub: str
    email: str
    name: str


class KeycloakUserVerifier:
    def __init__(self, jwks_url: str, issuer: str):
        self._verifier = RS256Verifier(JwksCache.from_url(jwks_url), audience=None, issuer=issuer)

    def verify(self, token: str) -> UserIdentity:
        claims = self._verifier.verify(token)
        if "email" not in claims:
            raise Unauthorized("token carries no email claim")
        return UserIdentity(claims["sub"], claims["email"].lower(), claims.get("name") or claims.get("preferred_username") or claims["email"])


class DevUserVerifier:
    """Development only: HS256 token minted by the web app's dev login. Refused in prod."""

    def __init__(self, secret: str):
        if is_prod():
            raise RuntimeError("the dev user verifier must not run in prod")
        self._secret = secret

    def verify(self, token: str) -> UserIdentity:
        try:
            c = jwt.decode(token, self._secret, algorithms=["HS256"], audience="credsort-identity-dev")
        except jwt.PyJWTError as exc:
            raise Unauthorized(f"invalid user token: {exc}") from exc
        return UserIdentity(c["sub"], c["email"].lower(), c.get("name", c["email"]))


def build_user_verifier():
    if env("USER_AUTH_MODE", "dev") == "keycloak":
        return KeycloakUserVerifier(env("KEYCLOAK_JWKS_URL", "") or "", env("KEYCLOAK_ISSUER", "") or "")
    return DevUserVerifier(env("DEV_USER_TOKEN_SECRET", "dev-only-user-secret-change-me-0123456789") or "")
