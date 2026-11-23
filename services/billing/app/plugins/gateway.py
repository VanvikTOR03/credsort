"""Payment gateway plug-in port (ADR-0003). The company's one-off CHF 190 fee is paid through a gateway.

The MVP ships a DEMO gateway: it supports the payment methods a real one would (TWINT, Visa, Mastercard) and always reports success
without moving money or accepting card details. A real provider (for example Stripe or Datatrans) implements the same port; the card
form of such a provider is hosted by the provider, so card numbers never reach CredSort.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from credsort_common.config import env, is_prod

METHODS = ("TWINT", "VISA", "MASTERCARD")


@dataclass(frozen=True)
class GatewayResult:
    provider: str
    reference: str
    approved: bool


class PaymentGateway(Protocol):
    name: str

    def charge(self, *, method: str, amount: Decimal, currency: str, idempotency_key: str) -> GatewayResult: ...


class DemoGateway:
    """Simulates an approved payment. Refused in production so that it can never stand in for a real charge."""
    name = "demo"

    def __init__(self) -> None:
        if is_prod():
            raise RuntimeError("the demo payment gateway must not run in prod")

    def charge(self, *, method: str, amount: Decimal, currency: str, idempotency_key: str) -> GatewayResult:
        if method not in METHODS:
            raise ValueError(f"unsupported payment method {method}")
        return GatewayResult(provider=self.name, reference=f"DEMO-{uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key).hex[:12].upper()}", approved=True)


def build_gateway() -> PaymentGateway:
    provider = env("PAYMENT_PROVIDER", "demo")
    if provider == "demo":
        return DemoGateway()
    raise RuntimeError(f"unknown PAYMENT_PROVIDER {provider!r}: implement the PaymentGateway port for it")
