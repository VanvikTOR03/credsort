"""bexio plug-in (ADR-0003). *** UNVERIFIED ***

The request/response shapes below follow bexio's public API as documented, but they have NOT been exercised against a sandbox
(needs the team's bexio developer app). Docs/architecture and the Master Plan list the bexio feasibility test (M2) as open work.
Until it passes, the synthetic plug-in is the supported source. Retry/timeout behaviour is implemented per ADR-0007.
"""
from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import httpx

from credsort_common.config import env

from ..domain.ledger import CanonicalLedger, Entry
from .base import ProviderError

BASE = env("BEXIO_API_BASE", "https://api.bexio.com") or "https://api.bexio.com"
ACCOUNTS_PATH = env("BEXIO_ACCOUNTS_PATH", "/2.0/accounts") or "/2.0/accounts"
JOURNAL_PATH = env("BEXIO_JOURNAL_PATH", "/3.0/accounting/journal") or "/3.0/accounting/journal"
PAGE = 500


class BexioProvider:
    def __init__(self, token_decrypt):
        self._decrypt = token_decrypt

    def _get(self, client: httpx.Client, path: str, params: dict) -> list[dict]:
        for attempt in range(3):
            try:
                resp = client.get(path, params=params)
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise ProviderError("PROVIDER_ERROR", str(exc)) from exc
                time.sleep(0.5 * 2 ** attempt)
                continue
            if resp.status_code in (401, 403):
                raise ProviderError("AUTH_ERROR", "bexio refused the credentials; reconnect bexio")  # never retried
            if resp.status_code in (429, 502, 503, 504):
                if attempt == 2:
                    raise ProviderError("PROVIDER_UNAVAILABLE", f"bexio answered {resp.status_code}")
                time.sleep(min(float(resp.headers.get("Retry-After", 1)), 10))
                continue
            resp.raise_for_status()
            return resp.json()
        raise ProviderError("PROVIDER_ERROR")

    def fetch(self, connection: dict, as_of: date) -> CanonicalLedger:
        token = self._decrypt(connection.get("token_enc"))
        if not token:
            raise ProviderError("AUTH_ERROR", "bexio is not connected")
        y2 = as_of.year - 1
        start, end = date(y2 - 1, 1, 1), date(y2, 12, 31)
        with httpx.Client(base_url=BASE, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                          timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            accounts_raw = self._get(client, ACCOUNTS_PATH, {"limit": 2000})
            accounts = {str(a["account_no"]): a.get("name", "") for a in accounts_raw}
            by_id = {a["id"]: str(a["account_no"]) for a in accounts_raw}
            entries: list[Entry] = []
            opening: dict[str, Decimal] = {}
            offset = 0
            while True:
                page = self._get(client, JOURNAL_PATH, {"limit": PAGE, "offset": offset})
                for row in page:
                    d, amount = date.fromisoformat(row["date"]), Decimal(str(row["amount"]))
                    debit, credit = by_id.get(row["debit_account_id"]), by_id.get(row["credit_account_id"])
                    if debit is None or credit is None:
                        raise ProviderError("MAPPING_ERROR", "journal entry references an unknown account")
                    if d < start:  # earlier history is folded into opening balances
                        opening[debit] = opening.get(debit, Decimal(0)) + amount
                        opening[credit] = opening.get(credit, Decimal(0)) - amount
                    elif d <= end:
                        entries.append(Entry(d, debit, credit, amount, str(row.get("ref_no") or row["id"])))
                if len(page) < PAGE:
                    break
                offset += PAGE
        return CanonicalLedger("BEXIO", start, end, accounts, opening, entries)


def exchange_code(code: str) -> str:
    """OAuth authorization-code exchange. UNVERIFIED against the real bexio app (see module docstring)."""
    try:
        resp = httpx.post(env("BEXIO_TOKEN_URL", "https://auth.bexio.com/realms/bexio/protocol/openid-connect/token"), timeout=10.0, data={
            "grant_type": "authorization_code", "code": code, "client_id": env("BEXIO_CLIENT_ID", ""), "client_secret": env("BEXIO_CLIENT_SECRET", ""),
            "redirect_uri": env("BEXIO_REDIRECT_URI", "http://localhost:3000/api/bexio/callback")})
        resp.raise_for_status()
        return resp.json()["access_token"]
    except (httpx.HTTPError, KeyError) as exc:
        raise ProviderError("PROVIDER_UNAVAILABLE", "bexio token exchange failed") from exc
