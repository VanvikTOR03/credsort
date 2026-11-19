"""Hash chain per organization stream (ADR-0028). The hash covers the record's identity and content, NOT personal references,
so personal references can be pseudonymised on deletion without breaking verification."""
from __future__ import annotations

import hashlib


def record_hash(prev_hash: str, org_id, seq: int, source_service: str, source_audit_id, action: str, resource: str, occurred_at_iso: str) -> str:
    material = "|".join([prev_hash, str(org_id), str(seq), source_service, str(source_audit_id), action, resource, occurred_at_iso])
    return hashlib.sha256(material.encode()).hexdigest()


LABELS = {
    "organization.created": "Organization created", "member.added": "Member added", "member.removed": "Member removed",
    "delegation.granted": "Access shared with a fiduciary", "delegation.revoked": "Fiduciary access ended",
    "connection.created": "Accounting source connected", "connection.revoked": "Accounting source disconnected",
    "import.requested": "Import started", "import.completed": "Accounting data imported", "import.failed": "Import failed", "ledger.read": "Data read to build your profile",
    "assessment.created": "Financial profile created", "assessment.failed": "Profile could not be built", "profile.extracted": "Shared fields prepared for publication",
    "advisory.context.read": "Figures read to explain your assessment", "scenario.created": "What-if scenario calculated", "explanation.created": "Explanation created",
    "application.created": "Application created", "application.updated": "Application edited", "application.published": "Application published to lenders",
    "application.withdrawn": "Application withdrawn", "application.viewed": "A lender viewed your shared information",
    "disclosure.revoked": "Sharing revoked", "access.requested": "A lender asked for more information", "access.approved": "More information shared with a lender",
    "access.denied": "Request for more information denied", "offer.submitted": "Offer received", "offer.withdrawn": "Offer withdrawn", "offer.selected": "Offer selected",
    "loan.funded": "Lender confirmed the payout", "loan.disputed": "Payout disputed", "loan.cancelled": "Loan cancelled", "criteria.saved": "Lending criteria saved",
    "charge.recorded": "Fee recorded", "charge.held": "Fee put on hold", "charge.waived": "Fee waived", "charge.cancelled": "Fee cancelled", "charge.recorded_": "Fee recorded",
    "price_book.created": "Price book created", "price_book.activated": "Price book activated", "entitlements.changed": "Plan features changed",
    "data.deleted": "Data deleted", "organization.deletion_requested": "Deletion requested", "organization.suspended": "Organization suspended",
    "organization.kyb.verified": "Organization verified", "organization.kyb.rejected": "Organization verification rejected",
}
