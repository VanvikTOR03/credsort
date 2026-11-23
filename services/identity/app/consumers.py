"""Identity consumes audit events to track coordinated deletion (ADR-0031)."""
from __future__ import annotations

from credsort_common.background import Consumer

from .service import confirm_deletion, run_identity_check


def deletion_tracker() -> Consumer:
    def handle(session, event):
        d = event["data"]
        if d.get("action") == "data.deleted":
            confirm_deletion(session, event["credsortorgid"], event["source"].rsplit("/", 1)[-1])
    return Consumer("identity-deletion-tracker", ["*.audit.recorded.*"], handle)


def kyc_runner(provider) -> Consumer:
    """Runs the partner identity check after the company paid the unlock fee (Billing event)."""
    return Consumer("identity-kyc", ["billing.unlock.paid.*"], lambda session, event: run_identity_check(session, provider, event))
