"""Money and ratio rules (ADR-0015): Decimal only, CHF, rounding at boundaries, decimals as strings."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

CHF = "CHF"
_Q4 = Decimal("0.0001")
_Q8 = Decimal("0.00000001")
_Q05 = Decimal("0.05")


def D(value) -> Decimal:
    """Parse to Decimal. Floats are refused so binary rounding errors can never enter."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("float is not allowed for money or ratios (ADR-0015)")
    return Decimal(str(value))


def q_amount(value) -> Decimal:
    return D(value).quantize(_Q4, rounding=ROUND_HALF_EVEN)


def q_ratio(value) -> Decimal:
    return D(value).quantize(_Q8, rounding=ROUND_HALF_EVEN)


def round_invoice_chf(value) -> Decimal:
    """Invoiced CHF amounts are rounded once, at the boundary, to 0.05 (to be confirmed with the accountant)."""
    d = D(value)
    return (d / _Q05).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * _Q05


def dstr(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _install_decimal_encoder() -> None:
    """FastAPI would serialize Decimal as a JSON float. Money and ratios are always strings (ADR-0015, FF-I8)."""
    from fastapi.encoders import ENCODERS_BY_TYPE
    ENCODERS_BY_TYPE[Decimal] = lambda d: format(d, "f")


_install_decimal_encoder()


def _parse(v):
    if isinstance(v, float):
        raise ValueError("decimal values must be sent as strings, not floats")
    return Decimal(str(v))


DecimalStr = Annotated[Decimal, BeforeValidator(_parse), PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json")]


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = CHF

    def __post_init__(self):
        if self.currency != CHF:
            raise ValueError("only CHF is supported in the MVP")
