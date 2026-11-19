from __future__ import annotations

from datetime import date
from typing import Protocol

from ..domain.ledger import CanonicalLedger


class ProviderError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class AccountingDataProvider(Protocol):
    """Anti-corruption port (ADR-0003): fetch from an external system and translate into the canonical ledger."""

    def fetch(self, connection: dict, as_of: date) -> CanonicalLedger: ...
