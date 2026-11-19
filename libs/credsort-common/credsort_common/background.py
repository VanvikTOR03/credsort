"""Outbox relay and idempotent consumers (ADR-0023). Run as background threads of each service process."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .broker import Broker
from .db import Database

log = logging.getLogger("credsort.background")


@dataclass
class Consumer:
    """`prefetch` runs BEFORE the transaction opens (remote calls never happen inside a transaction, ADR-0011);
    its result is passed to `handler` as a third argument."""
    name: str
    bindings: list[str]
    handler: Callable[..., None]
    prefetch: Callable[[dict], object] | None = None


class OutboxRelay(threading.Thread):
    """Publishes unsent outbox rows. Safe to run on several replicas (FOR UPDATE SKIP LOCKED). A row is marked sent
    only after the broker confirmed it; a crash in between causes a duplicate delivery which the inbox absorbs."""

    def __init__(self, db: Database, broker: Broker, stop: threading.Event, batch: int = 50):
        super().__init__(daemon=True, name=f"relay-{db.service}")
        self.db, self.broker, self.stop_event, self.batch = db, broker, stop, batch

    def drain_once(self) -> int:
        with self.db.system() as s:
            rows = s.execute(text("select id, payload from outbox where sent_at is null order by created_at, id limit :n "
                                  "for update skip locked"), {"n": self.batch}).all()
            for row in rows:
                self.broker.publish(row.payload)
                s.execute(text("update outbox set sent_at = now() where id = :i"), {"i": row.id})
            return len(rows)

    def run(self):
        while not self.stop_event.is_set():
            try:
                if self.drain_once() == 0:
                    time.sleep(0.3)
            except Exception:
                log.exception("outbox relay failed; events remain in the outbox")
                time.sleep(2)


def process_event(db: Database, consumer: Consumer, event: dict) -> bool:
    """Apply one event exactly once for this consumer. Returns False if it was a duplicate or tombstoned."""
    org = event.get("credsortorgid")
    prefetched = consumer.prefetch(event) if consumer.prefetch else None
    with db.session(org, "EVENT") as s:
        is_deletion = event["type"].startswith("credsort.identity.organization.deletion_requested")
        if not is_deletion and s.execute(text("select 1 from tombstones where org_id = :o"), {"o": org}).first():
            return False  # events of deleted organizations are never applied (ADR-0031, R-D3)
        inserted = s.execute(text("insert into inbox(consumer, event_id) values (:c, :e) on conflict do nothing"),
                             {"c": consumer.name, "e": event["id"]}).rowcount
        if not inserted:
            return False
        consumer.handler(s, event, prefetched) if consumer.prefetch else consumer.handler(s, event)
        return True


class ConsumerRunner(threading.Thread):
    def __init__(self, db: Database, broker: Broker, consumer: Consumer, stop: threading.Event):
        super().__init__(daemon=True, name=f"consumer-{consumer.name}")
        self.db, self.broker, self.consumer, self.stop_event = db, broker, consumer, stop
        broker.declare_consumer(consumer.name, consumer.bindings)

    def run(self):
        self.broker.consume(self.consumer.name, lambda ev: process_event(self.db, self.consumer, ev), self.stop_event)
