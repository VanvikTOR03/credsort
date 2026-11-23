"""Event catalogue: every event is THIN (IDs, states, versions) and has a strict JSON Schema (ADR-0023, FF-C5).

`contracts/events/*.schema.json` is generated from this file and checked in CI (FF-E4).
"""
from __future__ import annotations

import json
from pathlib import Path

_UUID = {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"}
_T = {
    "uuid": _UUID, "str": {"type": "string"}, "int": {"type": "integer"}, "date": {"type": "string"},
    "ts": {"type": "string"}, "uuid[]": {"type": "array", "items": _UUID}, "str[]": {"type": "array", "items": {"type": "string"}},
}

# Field names that must never appear in an event (strictly confidential catalogue, ADR-0023 / 08 §2).
FORBIDDEN_FIELDS = {
    "amount", "revenue", "metrics", "metric", "ledger", "email", "name", "legal_name", "rate", "fees", "score", "password",
    "token", "iban", "principal", "balance", "profit", "ebitda", "ratio", "value", "entries", "journal", "phone", "address",
}


def _field(spec: str) -> tuple[dict, bool]:
    optional = spec.endswith("?")
    spec = spec.rstrip("?")
    schema = {"enum": spec[5:].split("|")} if spec.startswith("enum:") else dict(_T[spec])
    if optional:
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema, not optional


def S(**fields: str) -> dict:
    props, required = {}, []
    for name, spec in fields.items():
        props[name], req = _field(spec)
        if req:
            required.append(name)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


AUDIT = S(audit_id="uuid", actor_user_id="uuid?", acting_org_id="uuid?", on_behalf_of_org_id="uuid?", action="str", resource="str")

CATALOG: dict[str, dict] = {
    "identity.organization.created": S(org_id="uuid", org_type="enum:SME|LENDER|FIDUCIARY|PLATFORM", referred_by_org_id="uuid?"),
    "identity.organization.verification_changed": S(org_id="uuid", kyb_status="enum:UNVERIFIED|PENDING|VERIFIED|REJECTED"),
    "identity.organization.kyc_completed": S(org_id="uuid", kyc_status="enum:VERIFIED|REJECTED"),
    "identity.organization.suspended": S(org_id="uuid"),
    "identity.membership.revoked": S(org_id="uuid", user_id="uuid", revoked_at="ts"),
    "identity.delegation.granted": S(sme_org_id="uuid", fiduciary_org_id="uuid", scopes="str[]"),
    "identity.delegation.revoked": S(sme_org_id="uuid", fiduciary_org_id="uuid"),
    "identity.organization.deletion_requested": S(org_id="uuid", requested_at="ts"),
    "identity.audit.recorded": AUDIT,
    "accounting.import.completed": S(org_id="uuid", batch_id="uuid", period_start="date", period_end="date", content_hash="str"),
    "accounting.import.failed": S(org_id="uuid", job_id="uuid", reason_code="str"),
    "accounting.connection.revoked": S(org_id="uuid", connection_id="uuid"),
    "accounting.audit.recorded": AUDIT,
    "intelligence.snapshot.created": S(org_id="uuid", snapshot_id="uuid", batch_id="uuid"),
    "intelligence.assessment.created": S(org_id="uuid", assessment_id="uuid", snapshot_id="uuid", scorecard_version="str", mapping_version="str"),
    "intelligence.assessment.failed": S(org_id="uuid", batch_id="uuid", reason_code="str"),
    "intelligence.audit.recorded": AUDIT,
    "marketplace.application.published": S(application_id="uuid", sme_org_id="uuid"),
    "marketplace.application.matched": S(application_id="uuid", sme_org_id="uuid", lender_org_ids="uuid[]"),
    "marketplace.application.withdrawn": S(application_id="uuid", sme_org_id="uuid"),
    "marketplace.application.closed": S(application_id="uuid", sme_org_id="uuid"),
    "marketplace.disclosure.granted": S(application_id="uuid", sme_org_id="uuid", lender_org_id="uuid?", level="enum:summary|full"),
    "marketplace.disclosure.revoked": S(application_id="uuid", sme_org_id="uuid", lender_org_id="uuid?", level="enum:summary|full"),
    "marketplace.access.requested": S(application_id="uuid", request_id="uuid", sme_org_id="uuid", lender_org_id="uuid"),
    "marketplace.access.decided": S(application_id="uuid", request_id="uuid", sme_org_id="uuid", lender_org_id="uuid", decision="enum:APPROVED|DENIED"),
    "marketplace.offer.submitted": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid"),
    "marketplace.offer.withdrawn": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid"),
    "marketplace.offer.selected": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid",
                                    other_lender_org_ids="uuid[]"),
    # The fee becomes payable only when the lender confirms the payout (ADR-0013); the SME has 14 days to dispute.
    "marketplace.loan.funded": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid", quote_ids="uuid[]"),
    "marketplace.loan.disputed": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid", quote_ids="uuid[]"),
    "marketplace.loan.cancelled": S(offer_id="uuid", application_id="uuid", sme_org_id="uuid", lender_org_id="uuid", quote_ids="uuid[]"),
    "marketplace.audit.recorded": AUDIT,
    "billing.price_book.activated": S(price_book_id="uuid", version="int"),
    "billing.entitlements.changed": S(org_id="uuid", entitlements="str[]"),
    "billing.charge.recorded": S(charge_id="uuid", org_id="uuid", quote_id="uuid"),
    "billing.charge.status_changed": S(charge_id="uuid", org_id="uuid", status="enum:RECORDED|HELD|WAIVED|CANCELLED"),
    "billing.unlock.paid": S(org_id="uuid", application_id="uuid", payment_id="uuid"),
    "billing.charge.held": S(org_id="uuid?", quote_id="uuid?", reason_code="str", source_event_id="uuid"),
    "billing.audit.recorded": AUDIT,
    "advisory.audit.recorded": AUDIT,
    "notification.audit.recorded": AUDIT,
    "audit.audit.recorded": AUDIT,
}


def event_type(name: str) -> str:
    return f"credsort.{name}.v1"


def schema_files() -> dict[str, dict]:
    return {f"{name}.v1.schema.json": {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": event_type(name),
                                        "title": name, **schema} for name, schema in CATALOG.items()}


def write_schemas(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for fname, doc in schema_files().items():
        (dest / fname).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
