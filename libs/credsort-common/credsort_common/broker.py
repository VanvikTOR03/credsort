"""Message brokers behind one interface (ADR-0023).

* RabbitMqBroker: topic exchange, quorum queues, delayed retry queue and DLQ per consumer (production / Compose).
* PgDevBroker: database-backed broker with the same semantics for machines without Docker (refused in prod).
* InMemoryBroker: synchronous broker for unit tests.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Callable, Protocol

from sqlalchemy import create_engine, text

from .config import is_prod

EXCHANGE = "credsort.events"
# Temporary failures (a service restarting, a database failing over) are retried over hours before a message is dead-lettered.
RETRY_SCHEDULE = [5, 30, 120, 600, 1800, 3600, 3600, 3600, 3600, 3600]  # seconds before attempt 2, 3, ...
MAX_ATTEMPTS = len(RETRY_SCHEDULE) + 1


def retry_delay(attempts_done: int) -> int:
    return RETRY_SCHEDULE[min(attempts_done - 1, len(RETRY_SCHEDULE) - 1)]


def routing_key(event_type: str) -> str:
    return event_type.removeprefix("credsort.")


def _pattern_to_regex(pattern: str) -> re.Pattern:
    out = ""
    for part in re.split(r"(\*|#)", pattern):
        out += {"*": r"[^.]+", "#": r".*"}.get(part, re.escape(part))
    return re.compile(f"^{out}$")


Handler = Callable[[dict], None]


class Broker(Protocol):
    def publish(self, event: dict) -> None: ...
    def declare_consumer(self, queue: str, patterns: list[str]) -> None: ...
    def consume(self, queue: str, handler: Handler, stop: threading.Event) -> None: ...


# --------------------------------------------------------------------------- in memory (tests)
class InMemoryBroker:
    def __init__(self):
        self.bindings: dict[str, list[re.Pattern]] = {}
        self.queues: dict[str, list[dict]] = {}
        self.dead: dict[str, list[dict]] = {}

    def declare_consumer(self, queue, patterns):
        self.bindings[queue] = [_pattern_to_regex(p) for p in patterns]
        self.queues.setdefault(queue, [])
        self.dead.setdefault(queue, [])

    def publish(self, event):
        key = routing_key(event["type"])
        for q, pats in self.bindings.items():
            if any(p.match(key) for p in pats):
                self.queues[q].append(json.loads(json.dumps(event)))

    def drain(self, queue: str, handler: Handler) -> int:
        n = 0
        while self.queues.get(queue):
            ev = self.queues[queue].pop(0)
            for attempt in range(MAX_ATTEMPTS):
                try:
                    handler(ev)
                    break
                except Exception:
                    if attempt == MAX_ATTEMPTS - 1:
                        self.dead[queue].append(ev)
            n += 1
        return n

    def consume(self, queue, handler, stop):
        while not stop.is_set():
            if not self.drain(queue, handler):
                time.sleep(0.05)


# --------------------------------------------------------------------------- dev broker (Postgres tables)
class PgDevBroker:
    """Dev/test only. Same semantics as the RabbitMQ topology: per-consumer queues, retries with delay, dead letters."""

    def __init__(self, url: str):
        if is_prod():
            raise RuntimeError("PgDevBroker is refused in prod; use RabbitMQ")
        self.engine = create_engine(url, isolation_level="AUTOCOMMIT", future=True, pool_size=4)
        with self.engine.connect() as c:
            c.execute(text("select pg_advisory_lock(727275)"))
            c.execute(text("create table if not exists bindings (queue text, pattern text, primary key (queue, pattern))"))
            c.execute(text("create table if not exists messages (id bigserial primary key, queue text not null, event jsonb not null, "
                           "attempts int not null default 0, available_at timestamptz not null default now(), dead boolean not null default false, "
                           "last_error text)"))
            c.execute(text("create index if not exists messages_ready on messages (queue, available_at) where not dead"))
            c.execute(text("select pg_advisory_unlock(727275)"))

    def declare_consumer(self, queue, patterns):
        with self.engine.begin() as c:
            for p in patterns:
                c.execute(text("insert into bindings(queue, pattern) values (:q, :p) on conflict do nothing"), {"q": queue, "p": p})

    def publish(self, event):
        key = routing_key(event["type"])
        with self.engine.begin() as c:
            rows = c.execute(text("select queue, pattern from bindings")).all()
            queues = {q for q, p in rows if _pattern_to_regex(p).match(key)}
            for q in queues:
                c.execute(text("insert into messages(queue, event) values (:q, cast(:e as jsonb))"), {"q": q, "e": json.dumps(event)})

    def consume(self, queue, handler, stop):
        while not stop.is_set():
            claimed = None
            with self.engine.begin() as c:
                row = c.execute(text("select id, event, attempts from messages where queue = :q and not dead and available_at <= now() "
                                     "order by id limit 1 for update skip locked"), {"q": queue}).first()
                if row:
                    # lease the message for 30 s so another consumer does not pick it up while we handle it
                    c.execute(text("update messages set available_at = now() + interval '30 seconds' where id = :i"), {"i": row.id})
                    claimed = row
            if claimed is None:
                time.sleep(0.2)
                continue
            try:
                handler(claimed.event)
                with self.engine.begin() as c:
                    c.execute(text("delete from messages where id = :i"), {"i": claimed.id})
            except Exception as exc:
                attempts = claimed.attempts + 1
                with self.engine.begin() as c:
                    c.execute(text("update messages set attempts = :a, last_error = :e, dead = :d, "
                                   "available_at = now() + make_interval(secs => :s) where id = :i"),
                              {"a": attempts, "e": str(exc)[:500], "d": attempts >= MAX_ATTEMPTS, "s": retry_delay(attempts), "i": claimed.id})


# --------------------------------------------------------------------------- RabbitMQ
class RabbitMqBroker:
    """AMQP 0-9-1 topology: topic exchange `credsort.events`; per consumer a quorum queue `q.<name>`, a retry queue
    `q.<name>.retry.<seconds>` (TTL queues, dead-letter back to the main queue) and `q.<name>.dlq`. Publisher confirms are enabled."""

    def __init__(self, url: str):
        import pika  # imported lazily so unit tests do not need a broker
        self._pika = pika
        self._params = pika.URLParameters(url)
        self._pub = None
        self._lock = threading.Lock()

    def _connect(self):
        conn = self._pika.BlockingConnection(self._params)
        ch = conn.channel()
        ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
        return conn, ch

    def publish(self, event):
        with self._lock:
            for attempt in range(2):
                try:
                    if self._pub is None or self._pub[0].is_closed or self._pub[1].is_closed:
                        conn, ch = self._connect()
                        ch.confirm_delivery()
                        self._pub = (conn, ch)
                    self._pub[1].basic_publish(EXCHANGE, routing_key(event["type"]), json.dumps(event).encode(),
                                               properties=self._pika.BasicProperties(content_type="application/cloudevents+json",
                                                                                      delivery_mode=2, message_id=event["id"]),
                                               mandatory=False)
                    return
                except Exception:
                    self._pub = None
                    if attempt == 1:
                        raise

    def declare_consumer(self, queue, patterns):
        conn, ch = self._connect()
        try:
            main = f"q.{queue}"
            ch.queue_declare(main, durable=True, arguments={"x-queue-type": "quorum"})
            for delay in sorted(set(RETRY_SCHEDULE)):
                ch.queue_declare(f"{main}.retry.{delay}", durable=True, arguments={
                    "x-queue-type": "quorum", "x-message-ttl": delay * 1000,
                    "x-dead-letter-exchange": "", "x-dead-letter-routing-key": main})
            ch.queue_declare(f"{main}.dlq", durable=True, arguments={"x-queue-type": "quorum"})
            for p in patterns:
                ch.queue_bind(main, EXCHANGE, p)
        finally:
            conn.close()

    def consume(self, queue, handler, stop):
        main = f"q.{queue}"
        while not stop.is_set():
            try:
                conn, ch = self._connect()
                ch.basic_qos(prefetch_count=10)
                for method, props, body in ch.consume(main, inactivity_timeout=0.5):
                    if stop.is_set():
                        break
                    if method is None:
                        continue
                    headers = dict(props.headers or {})
                    attempts = int(headers.get("x-attempts", 0))
                    try:
                        handler(json.loads(body))
                    except Exception as exc:
                        attempts += 1
                        headers.update({"x-attempts": attempts, "x-last-error": str(exc)[:500]})
                        target = f"{main}.dlq" if attempts >= MAX_ATTEMPTS else f"{main}.retry.{retry_delay(attempts)}"
                        ch.basic_publish("", target, body, properties=self._pika.BasicProperties(headers=headers, delivery_mode=2))
                    ch.basic_ack(method.delivery_tag)
                conn.close()
            except Exception:
                time.sleep(2)  # broker unavailable: events wait safely in outboxes


def make_broker(url: str) -> Broker:
    if url.startswith("pgdev://"):
        return PgDevBroker(url.removeprefix("pgdev://"))
    if url.startswith("amqp"):
        return RabbitMqBroker(url)
    raise ValueError(f"unsupported BROKER_URL: {url!r}")
