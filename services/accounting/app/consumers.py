from __future__ import annotations

from credsort_common.background import Consumer

from . import service as svc


def deletion_consumer() -> Consumer:
    return Consumer("accounting-deletion", ["identity.organization.deletion_requested.*"],
                    lambda session, event: svc.delete_org_data(session, event["credsortorgid"]))
