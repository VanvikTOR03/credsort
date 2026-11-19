"""KYB plug-in port (ADR-0020). The MVP ships a stub; a Swiss KYB vendor replaces it behind the same port."""
from __future__ import annotations

import re
from typing import Protocol

UID_PATTERN = re.compile(r"^CHE-\d{3}\.\d{3}\.\d{3}$")


class KybProvider(Protocol):
    def verify(self, org_type: str, uid: str | None, legal_name: str) -> str:
        """Returns UNVERIFIED | PENDING | VERIFIED | REJECTED."""


class StubKybProvider:
    """Verifies synthetic SMEs with a well-formed UID; lenders and fiduciaries wait for a platform admin."""

    def verify(self, org_type: str, uid: str | None, legal_name: str) -> str:
        if org_type == "SME" and uid and UID_PATTERN.match(uid):
            return "VERIFIED"
        if org_type == "PLATFORM":
            return "VERIFIED"
        return "PENDING"
