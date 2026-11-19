"""Separate import-worker deployment (ADR-0005): `python -m app.worker_main`."""
from __future__ import annotations

import threading

from credsort_common.broker import make_broker
from credsort_common.background import OutboxRelay
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.logging_setup import configure

from .worker import ImportWorker


def main() -> None:
    configure("accounting-worker")
    settings = Settings.from_env("accounting")
    db = Database(settings.database_url, "accounting")
    stop = threading.Event()
    if settings.broker_url:  # a relay here publishes the events the worker writes; running several relays is safe (SKIP LOCKED)
        OutboxRelay(db, make_broker(settings.broker_url), stop).start()
    ImportWorker(db, stop).run()


if __name__ == "__main__":
    main()
