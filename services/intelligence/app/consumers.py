from __future__ import annotations

from datetime import date

from credsort_common.background import Consumer
from credsort_common.errors import UpstreamHTTPError
from credsort_common.security import Security

from . import service as svc
from .clients import accounting_client


def pipeline_consumer(sec: Security, as_of=date.today, client=None) -> Consumer:
    client = client or accounting_client(sec)

    def prefetch(event: dict):  # claim check: runs BEFORE the transaction opens (ADR-0011)
        d = event["data"]
        try:
            return client.get(f"/internal/v1/batches/{d['batch_id']}/ledger", params={"org_id": event["credsortorgid"]})
        except UpstreamHTTPError as exc:
            if exc.upstream_status == 404:
                return None  # batch is gone (e.g. organization deleted): record a failure, never resurrect data
            raise

    def handle(session, event: dict, ledger):
        d = event["data"]
        if ledger is None:
            svc._failure(session, event["credsortorgid"], d["batch_id"], "BATCH_GONE")
            return
        svc.run_pipeline(session, event["credsortorgid"], ledger, as_of())

    return Consumer("intelligence-pipeline", ["accounting.import.completed.*"], handle, prefetch)


def entitlement_consumer() -> Consumer:
    return Consumer("intelligence-entitlements", ["billing.entitlements.changed.*"], svc.upsert_entitlements)


def deletion_consumer() -> Consumer:
    return Consumer("intelligence-deletion", ["identity.organization.deletion_requested.*"],
                    lambda session, event: svc.delete_org_data(session, event["credsortorgid"]))
