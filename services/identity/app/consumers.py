"""Identity consumes audit events to track coordinated deletion (ADR-0031)."""
from __future__ import annotations

from credsort_common.background import Consumer

from .service import confirm_deletion


def deletion_tracker() -> Consumer:
    def handle(session, event):
        d = event["data"]
        if d.get("action") == "data.deleted":
            confirm_deletion(session, event["credsortorgid"], event["source"].rsplit("/", 1)[-1])
    return Consumer("identity-deletion-tracker", ["*.audit.recorded.*"], handle)
