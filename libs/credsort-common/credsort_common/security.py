"""Context tokens, service identity and request authorization (ADR-0016, ADR-0027).

* Identity signs short-lived **context tokens** (RS256, about 2 minutes). Every service verifies them
  locally (cached JWKS), checks audience, expiry and the deny-list. Keycloak user tokens are NOT accepted
  by domain services.
* Internal endpoints additionally require a **service token** from an allowed caller.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, Header, Request

from .config import environment, env, is_prod
from .errors import Forbidden, Unauthorized

CONTEXT_AUDIENCE = "credsort-services"
CONTEXT_ISSUER = "credsort-identity"
CONTEXT_TTL_SECONDS = 120


# --------------------------------------------------------------------------- keys
class KeyStore:
    """Signing key (private) plus verification keys (current + previous, for rotation overlap)."""

    def __init__(self, private_key: rsa.RSAPrivateKey, previous_public_pems: list[bytes] | None = None):
        self._private = private_key
        self.kid = self._kid(private_key.public_key())
        self._public = {self.kid: private_key.public_key()}
        for pem in previous_public_pems or []:
            pub = serialization.load_pem_public_key(pem)
            self._public[self._kid(pub)] = pub

    @staticmethod
    def _kid(pub) -> str:
        numbers = pub.public_numbers()
        return hashlib.sha256(f"{numbers.n}:{numbers.e}".encode()).hexdigest()[:16]

    @classmethod
    def generate(cls) -> "KeyStore":
        return cls(rsa.generate_private_key(public_exponent=65537, key_size=2048))

    @classmethod
    def from_env(cls, name: str, dev_dir: str | None = None) -> "KeyStore":
        """Load the PEM from `<NAME>_SIGNING_KEY_PEM` (secret manager in the pilot). In dev a key is generated and
        persisted locally; in prod a missing key is a startup error."""
        pem = env(f"{name.upper()}_SIGNING_KEY_PEM")
        if pem:
            return cls(serialization.load_pem_private_key(pem.encode(), password=None))
        if is_prod():
            raise RuntimeError(f"{name.upper()}_SIGNING_KEY_PEM is required in prod")
        path = Path(dev_dir or env("CREDSORT_KEY_DIR", ".dev/keys") or ".dev/keys") / f"{name}.pem"
        if path.exists():
            return cls(serialization.load_pem_private_key(path.read_bytes(), password=None))
        store = cls.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store._private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                       serialization.NoEncryption()))
        return store

    def sign(self, claims: dict) -> str:
        return jwt.encode(claims, self._private, algorithm="RS256", headers={"kid": self.kid})

    def public_key(self, kid: str):
        return self._public.get(kid)

    def jwks(self) -> dict:
        keys = []
        for kid, pub in self._public.items():
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(pub))
            jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
            keys.append(jwk)
        return {"keys": keys}


class JwksCache:
    """Fetches and caches a JWKS document; refreshes on unknown kid (at most every 10 seconds)."""

    def __init__(self, fetch: Callable[[], dict], ttl: float = 300.0):
        self._fetch, self._ttl = fetch, ttl
        self._keys: dict[str, object] = {}
        self._loaded = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_url(cls, url: str) -> "JwksCache":
        def fetch() -> dict:
            return httpx.get(url, timeout=3.0).raise_for_status().json()
        return cls(fetch)

    @classmethod
    def static(cls, keystore: KeyStore) -> "JwksCache":
        return cls(keystore.jwks, ttl=10**9)

    def _refresh(self) -> None:
        doc = self._fetch()
        self._keys = {k["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k)) for k in doc["keys"]}
        self._loaded = time.time()

    def get(self, kid: str):
        with self._lock:
            if kid not in self._keys or time.time() - self._loaded > self._ttl:
                if time.time() - self._loaded > 10 or not self._keys:
                    try:
                        self._refresh()
                    except Exception:
                        if not self._keys:
                            raise
            return self._keys.get(kid)


class RS256Verifier:
    def __init__(self, jwks: JwksCache, *, audience: str | None, issuer: str | None):
        self.jwks, self.audience, self.issuer = jwks, audience, issuer

    def verify(self, token: str) -> dict:
        try:
            kid = jwt.get_unverified_header(token).get("kid", "")
            key = self.jwks.get(kid)
            if key is None:
                raise Unauthorized("unknown signing key")
            opts = {"require": ["exp", "iat"], "verify_aud": self.audience is not None}
            return jwt.decode(token, key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer, options=opts)
        except jwt.PyJWTError as exc:
            raise Unauthorized(f"invalid token: {exc}") from exc


# --------------------------------------------------------------------------- context
@dataclass(frozen=True)
class AccessContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    org_type: str
    org_name: str
    role: str
    scopes: tuple[str, ...] = ()
    on_behalf_of: uuid.UUID | None = None
    kyb_status: str = "UNVERIFIED"
    industry: str | None = None
    employees: int | None = None
    jti: str = ""
    iat: int = 0
    raw: str = field(default="", repr=False)

    @property
    def effective_org_id(self) -> uuid.UUID:
        """The organization whose data is being accessed (the SME when a fiduciary acts on its behalf)."""
        return self.on_behalf_of or self.org_id

    @property
    def delegated(self) -> bool:
        return self.on_behalf_of is not None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def context_from_claims(claims: dict, raw: str = "") -> AccessContext:
    try:
        return AccessContext(
            user_id=uuid.UUID(claims["sub"]), org_id=uuid.UUID(claims["org_id"]), org_type=claims["org_type"],
            org_name=claims.get("org_name", ""), role=claims["role"], scopes=tuple(claims.get("scopes", [])),
            on_behalf_of=uuid.UUID(claims["on_behalf_of"]) if claims.get("on_behalf_of") else None,
            kyb_status=claims.get("kyb_status", "UNVERIFIED"), industry=claims.get("industry"),
            employees=claims.get("employees"), jti=claims.get("jti", ""), iat=int(claims.get("iat", 0)), raw=raw)
    except (KeyError, ValueError) as exc:
        raise Unauthorized("malformed context token") from exc


def new_context_claims(*, user_id, org_id, org_type, org_name, role, scopes=(), on_behalf_of=None, kyb_status="UNVERIFIED",
                       industry=None, employees=None, now: int | None = None) -> dict:
    iat = now or int(time.time())
    claims = {"iss": CONTEXT_ISSUER, "aud": CONTEXT_AUDIENCE, "iat": iat, "exp": iat + CONTEXT_TTL_SECONDS,
              "jti": uuid.uuid4().hex, "sub": str(user_id), "org_id": str(org_id), "org_type": org_type,
              "org_name": org_name, "role": role, "scopes": list(scopes), "kyb_status": kyb_status}
    if on_behalf_of:
        claims["on_behalf_of"] = str(on_behalf_of)
    if industry:
        claims["industry"] = industry
    if employees is not None:
        claims["employees"] = employees
    return claims


# --------------------------------------------------------------------------- authz helpers
def require_role(ctx: AccessContext, *roles: str) -> None:
    if ctx.role not in roles:
        raise Forbidden(f"role {ctx.role} may not perform this action", code="role_forbidden")


def require_org_type(ctx: AccessContext, *types: str) -> None:
    if ctx.org_type not in types:
        raise Forbidden(f"{ctx.org_type} organizations may not perform this action", code="org_type_forbidden")


def require_verified(ctx: AccessContext) -> None:
    if ctx.kyb_status != "VERIFIED":
        raise Forbidden("organization verification (KYB) is required", code="kyb_required")


def forbid_delegated(ctx: AccessContext) -> None:
    """Delegation never includes selecting offers or granting disclosure (ADR-0019)."""
    if ctx.delegated:
        raise Forbidden("this action cannot be performed on behalf of another organization", code="delegation_forbidden")


def require_scope_if_delegated(ctx: AccessContext, scope: str) -> None:
    if ctx.delegated and not ctx.has_scope(scope):
        raise Forbidden(f"delegation does not include {scope}", code="scope_missing")


def require_sme_access(ctx: AccessContext, scope: str | None = None) -> None:
    """The caller is the SME itself, or a fiduciary acting under a delegation that includes `scope` (ADR-0019)."""
    if ctx.org_type == "SME":
        return
    if ctx.org_type == "FIDUCIARY" and ctx.delegated and (scope is None or ctx.has_scope(scope)):
        return
    raise Forbidden("this action requires access to the SME's data", code="sme_access_required")


# --------------------------------------------------------------------------- service identity
class ServiceAuth:
    """Service-to-service identity.

    prod/keycloak: OAuth2 client credentials against Keycloak (verified by `azp`).
    dev: HS256 tokens signed with SERVICE_TOKEN_SECRET (refused in prod).
    """

    def __init__(self, service: str):
        self.service = service
        self.mode = env("SERVICE_AUTH_MODE", "dev")
        if self.mode == "dev" and is_prod():
            raise RuntimeError("dev service tokens are refused in prod")
        self._secret = env("SERVICE_TOKEN_SECRET", "dev-only-service-secret-change-me-0123456789")
        self._cached: tuple[str, float] | None = None
        self._jwks: JwksCache | None = None

    def issue(self, target: str) -> str:
        if self.mode == "keycloak":
            return self._client_credentials()
        now = int(time.time())
        return jwt.encode({"svc": self.service, "aud": f"svc:{target}", "iat": now, "exp": now + 60}, self._secret, algorithm="HS256")

    def verify(self, token: str, expected_audience: str) -> str:
        """Returns the calling service name."""
        try:
            if self.mode == "keycloak":
                if self._jwks is None:
                    self._jwks = JwksCache.from_url(env("KEYCLOAK_JWKS_URL", "") or "")
                claims = RS256Verifier(self._jwks, audience=None, issuer=env("KEYCLOAK_ISSUER")).verify(token)
                client = claims.get("azp", "")
                return client.removeprefix("svc-")
            claims = jwt.decode(token, self._secret, algorithms=["HS256"], audience=f"svc:{expected_audience}")
            return claims["svc"]
        except jwt.PyJWTError as exc:
            raise Unauthorized(f"invalid service token: {exc}") from exc

    def _client_credentials(self) -> str:
        if self._cached and self._cached[1] > time.time() + 15:
            return self._cached[0]
        resp = httpx.post(env("KEYCLOAK_TOKEN_URL", "") or "", timeout=3.0, data={
            "grant_type": "client_credentials", "client_id": f"svc-{self.service}",
            "client_secret": env("SERVICE_CLIENT_SECRET", "") or ""})
        resp.raise_for_status()
        body = resp.json()
        self._cached = (body["access_token"], time.time() + int(body.get("expires_in", 60)))
        return self._cached[0]


# --------------------------------------------------------------------------- deny-list
class Denylist:
    """Revoked memberships / delegations and suspended organizations, fed by identity events (ADR-0027).

    Rows are (user_id, org_id, on_behalf_of, since). A token is denied if it was issued at or before `since` and matches:
    * user + org (membership revoked), * org only (organization suspended), * org + on_behalf_of (delegation revoked).
    """

    def __init__(self, load: Callable[[], list[tuple]], ttl: float = 5.0):
        self._load, self._ttl = load, ttl
        self._rows: list[tuple] = []
        self._at = 0.0

    def invalidate(self) -> None:
        self._at = 0.0

    def is_denied(self, user_id: uuid.UUID, org_id: uuid.UUID, issued_at: int, on_behalf_of: uuid.UUID | None = None) -> bool:
        if time.time() - self._at > self._ttl:
            try:
                self._rows, self._at = self._load(), time.time()
            except Exception:
                pass
        for row in self._rows:
            u, o, behalf, since = row if len(row) == 4 else (*row[:2], None, row[2])
            if issued_at > since:
                continue
            if behalf is not None:
                if o == org_id and behalf == on_behalf_of:
                    return True
            elif (u == user_id and (o is None or o == org_id)) or (u is None and o == org_id):
                return True
        return False


@dataclass
class Security:
    """Bundle of the verification pieces a service needs; injectable for tests."""
    service: str
    context_verifier: RS256Verifier
    denylist: Denylist
    service_auth: ServiceAuth

    def context_dependency(self):
        def _ctx(request: Request, authorization: str | None = Header(default=None)) -> AccessContext:
            if not authorization or not authorization.lower().startswith("bearer "):
                raise Unauthorized("missing bearer context token")
            raw = authorization.split(" ", 1)[1].strip()
            claims = self.context_verifier.verify(raw)
            ctx = context_from_claims(claims, raw)
            if self.denylist.is_denied(ctx.user_id, ctx.org_id, ctx.iat, ctx.on_behalf_of):
                raise Unauthorized("access revoked", code="revoked")
            request.state.ctx = ctx
            return ctx
        return _ctx

    def service_dependency(self, allowed_callers: set[str]):
        def _svc(x_service_token: str | None = Header(default=None)) -> str:
            if not x_service_token:
                raise Unauthorized("missing service token")
            caller = self.service_auth.verify(x_service_token, self.service)
            if caller not in allowed_callers:
                raise Forbidden(f"service {caller} may not call this endpoint", code="caller_forbidden")
            return caller
        return _svc


def build_security(service: str, denylist: Denylist) -> Security:
    from .config import service_url
    jwks = JwksCache.from_url(f"{service_url('identity')}/.well-known/jwks.json")
    return Security(service, RS256Verifier(jwks, audience=CONTEXT_AUDIENCE, issuer=CONTEXT_ISSUER), denylist, ServiceAuth(service))


Ctx = Depends  # re-exported alias for readability in routers
