from __future__ import annotations

from credsort_common.security import Security
from credsort_common.upstream import UpstreamClient


def accounting_client(sec: Security) -> UpstreamClient:
    return UpstreamClient("intelligence", "accounting", sec.service_auth, read_timeout=30.0)


def billing_client(sec: Security) -> UpstreamClient:
    return UpstreamClient("intelligence", "billing", sec.service_auth)
