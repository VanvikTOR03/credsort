from __future__ import annotations

from credsort_common.background import Consumer

from . import service as svc


def consumers() -> list[Consumer]:
    return [
        Consumer("billing-funded", ["marketplace.loan.funded.*"], svc.record_charges),
        Consumer("billing-disputed", ["marketplace.loan.disputed.*"], svc.hold_charges),
        Consumer("billing-cancelled", ["marketplace.loan.cancelled.*"], svc.cancel_charges),
        Consumer("billing-referrals", ["identity.organization.created.*"], svc.store_referral),
        Consumer("billing-deletion", ["identity.organization.deletion_requested.*"], lambda s, e: svc.delete_org_data(s, e["credsortorgid"])),
    ]
