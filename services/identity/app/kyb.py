"""KYB plug-in port (ADR-0020). The MVP ships a stub; a Swiss KYB vendor replaces it behind the same port."""
from __future__ import annotations

import re
from typing import Protocol

UID_PATTERN = re.compile(r"^CHE-\d{3}\.\d{3}\.\d{3}$")


class KybProvider(Protocol):
    def verify(self, org_type: str, uid: str | None, legal_name: str) -> str:
        """Returns UNVERIFIED | PENDING | VERIFIED | REJECTED."""


class IdentityProvider(Protocol):
    def verify_identity(self, org_id: str, legal_name: str, uid: str | None) -> str:
        """Partner identity check of the company's representative. Returns VERIFIED | REJECTED."""


class StubKybProvider:
    """Verifies synthetic SMEs with a well-formed UID; lenders and fiduciaries wait for a platform admin."""

    def verify(self, org_type: str, uid: str | None, legal_name: str) -> str:
        if org_type == "SME" and uid and UID_PATTERN.match(uid):
            return "VERIFIED"
        if org_type == "PLATFORM":
            return "VERIFIED"
        return "PENDING"


class StubIdentityProvider:
    """Demo identity check: approves companies with a well-formed UID. A real partner (video or e-ID) replaces it behind the same port."""

    def verify_identity(self, org_id: str, legal_name: str, uid: str | None) -> str:
        return "VERIFIED" if uid and UID_PATTERN.match(uid) else "REJECTED"
