from __future__ import annotations

from credsort_common.config import service_url
from credsort_common.security import (JwksCache, RS256Verifier, Security)
from credsort_common.upstream import UpstreamClient

QUOTE_AUD, QUOTE_ISS = "credsort-quotes", "credsort-billing"


def intelligence_client(sec: Security) -> UpstreamClient:
    return UpstreamClient("marketplace", "intelligence", sec.service_auth)


def billing_client(sec: Security) -> UpstreamClient:
    return UpstreamClient("marketplace", "billing", sec.service_auth)


def quote_verifier() -> RS256Verifier:
    """Quotes are verified LOCALLY with Billing's public key: no Billing call is needed at selection time (ADR-0013)."""
    return RS256Verifier(JwksCache.from_url(f"{service_url('billing')}/.well-known/jwks.json"), audience=QUOTE_AUD, issuer=QUOTE_ISS)
