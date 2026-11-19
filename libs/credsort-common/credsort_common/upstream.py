"""Resilient synchronous calls between services (ADR-0007) restricted to the fixed call inventory (ADR-0001, 06 §2).

Every call has timeouts, a circuit breaker and a separate connection pool per upstream (bulkhead). Only idempotent GETs are
retried; 401/403 are never retried. No call may be made inside a database transaction (caller's responsibility, checked in review).
"""
from __future__ import annotations

import random
import re
import threading
import time

import httpx

from .config import service_url
from .errors import UpstreamHTTPError, UpstreamUnavailable
from .reqctx import child_traceparent, request_id, traceparent
from .security import AccessContext, ServiceAuth

# (caller, target) -> allowed "METHOD path-template" entries. Mirrors docs/architecture/06 §2. FF-E6 verifies it statically.
CALL_INVENTORY: dict[tuple[str, str], list[str]] = {
    ("intelligence", "accounting"): ["GET /internal/v1/batches/{id}/ledger"],
    ("marketplace", "intelligence"): ["GET /internal/v1/assessments/{id}/profile-extract"],
    ("marketplace", "billing"): ["POST /internal/v1/quotes", "GET /.well-known/jwks.json"],
    ("advisory", "intelligence"): ["GET /internal/v1/assessments/{id}/advisory-context"],
    ("intelligence", "billing"): ["GET /internal/v1/organizations/{id}/entitlements"],
    ("advisory", "billing"): ["GET /internal/v1/organizations/{id}/entitlements"],
}
JWKS_CALLS = {"GET /.well-known/jwks.json"}  # C2: any service -> identity (key distribution)


def _template_regex(template: str) -> re.Pattern:
    return re.compile("^" + re.sub(r"\\\{[a-z_]+\\\}", "[^/]+", re.escape(template)) + "$")


class CircuitBreaker:
    def __init__(self, threshold: int = 5, reset_seconds: float = 30.0):
        self.threshold, self.reset = threshold, reset_seconds
        self.failures, self.opened_at = 0, 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.failures < self.threshold:
                return True
            return time.time() - self.opened_at >= self.reset  # half-open: let one probe through

    def success(self) -> None:
        with self._lock:
            self.failures = 0

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.time()


class UpstreamClient:
    def __init__(self, caller: str, target: str, auth: ServiceAuth, *, base_url: str | None = None,
                 connect_timeout: float = 2.0, read_timeout: float = 3.0, transport: httpx.BaseTransport | None = None):
        self.caller, self.target, self.auth = caller, target, auth
        self.base_url = (base_url or service_url(target)).rstrip("/")
        self.breaker = CircuitBreaker()
        self.client = httpx.Client(base_url=self.base_url, transport=transport,
                                   timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
                                   limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))

    def _allowed(self, method: str, path: str) -> None:
        entry = f"{method} {path}"
        if entry in JWKS_CALLS and self.target in ("identity", "billing"):
            return
        for template in CALL_INVENTORY.get((self.caller, self.target), []):
            m, tpl = template.split(" ", 1)
            if m == method and _template_regex(tpl).match(path):
                return
        raise PermissionError(f"call {self.caller} -> {self.target} {entry} is not in the allowed call inventory")

    def request(self, method: str, path: str, *, ctx: AccessContext | None = None, params: dict | None = None,
                json: dict | None = None, timeout: float | None = None) -> dict:
        self._allowed(method, path)
        if not self.breaker.allow():
            raise UpstreamUnavailable(f"{self.target} is temporarily unavailable (circuit open)", code="circuit_open")
        headers = {"X-Service-Token": self.auth.issue(self.target), "X-Request-Id": request_id(),
                   "traceparent": child_traceparent(traceparent())}
        if ctx is not None:
            headers["Authorization"] = f"Bearer {ctx.raw}"
        attempts = 3 if method == "GET" else 1
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = self.client.request(method, path, params=params, json=json, headers=headers,
                                           timeout=timeout if timeout else httpx.USE_CLIENT_DEFAULT)
            except httpx.HTTPError as exc:
                last = exc
                self.breaker.failure()
            else:
                if resp.status_code in (429, 502, 503, 504):
                    self.breaker.failure()
                    last = UpstreamUnavailable(f"{self.target} answered {resp.status_code}")
                elif resp.status_code >= 400:
                    if resp.status_code >= 500:
                        self.breaker.failure()
                    else:
                        self.breaker.success()  # client errors are not an upstream health problem
                    try:
                        problem = resp.json()
                    except ValueError:
                        problem = {}
                    raise UpstreamHTTPError(resp.status_code, problem.get("detail", ""), problem=problem)
                else:
                    self.breaker.success()
                    return resp.json() if resp.content else {}
            if attempt < attempts - 1:
                time.sleep(min(0.2 * (2 ** attempt), 1.0) + random.random() * 0.1)
        raise UpstreamUnavailable(f"{self.target} is unavailable: {last}", code="upstream_unavailable")

    def get(self, path: str, **kw) -> dict:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> dict:
        return self.request("POST", path, **kw)
