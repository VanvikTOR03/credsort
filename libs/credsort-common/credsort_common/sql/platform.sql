-- Platform tables applied to every service database (ADR-0004, ADR-0011, ADR-0023, ADR-0028).
create or replace function app_org() returns uuid language sql stable as
$$ select nullif(current_setting('app.org_id', true), '')::uuid $$;

create or replace function app_role() returns text language sql stable as
$$ select coalesce(nullif(current_setting('app.role', true), ''), 'NONE') $$;

create table if not exists schema_migrations (version text primary key, applied_at timestamptz not null default now());

-- Transactional outbox: written in the same transaction as the state change.
create table if not exists outbox (
    id uuid primary key,
    event_type text not null,
    org_id uuid not null,
    subject text not null,
    aggregate_version int not null default 1,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    sent_at timestamptz
);
create index if not exists outbox_unsent on outbox (created_at) where sent_at is null;
alter table outbox enable row level security;
alter table outbox force row level security;
drop policy if exists outbox_insert on outbox;
create policy outbox_insert on outbox for insert with check (true);
drop policy if exists outbox_system on outbox;
create policy outbox_system on outbox for all using (app_role() = 'SYSTEM') with check (app_role() = 'SYSTEM');

-- Idempotent inbox: one row per (consumer, event) in the same transaction as the side effect.
create table if not exists inbox (
    consumer text not null,
    event_id uuid not null,
    processed_at timestamptz not null default now(),
    primary key (consumer, event_id)
);

-- Deny-list of revoked memberships / suspended organizations (fed by identity events).
create table if not exists denylist (
    id bigserial primary key,
    user_id uuid,
    org_id uuid,
    on_behalf_of uuid,
    since timestamptz not null default now()
);

-- Local audit records written in the business transaction, forwarded to the central Audit service.
create table if not exists audit_records (
    id uuid primary key,
    org_id uuid not null,
    actor_user_id uuid,
    acting_org_id uuid,
    on_behalf_of_org_id uuid,
    action text not null,
    resource text not null,
    request_id text,
    occurred_at timestamptz not null default now()
);
create index if not exists audit_records_org on audit_records (org_id, occurred_at);
alter table audit_records enable row level security;
alter table audit_records force row level security;
drop policy if exists tenant on audit_records;
create policy tenant on audit_records using (org_id = app_org() or app_role() = 'SYSTEM')
    with check (true);

-- Idempotency keys for mutating external endpoints (24 h).
create table if not exists idempotency_keys (
    org_id uuid not null,
    key text not null,
    fingerprint text not null,
    status_code int not null,
    response jsonb not null,
    created_at timestamptz not null default now(),
    primary key (org_id, key)
);
alter table idempotency_keys enable row level security;
alter table idempotency_keys force row level security;
drop policy if exists tenant on idempotency_keys;
create policy tenant on idempotency_keys using (org_id = app_org() or app_role() = 'SYSTEM')
    with check (org_id = app_org() or app_role() = 'SYSTEM');

-- Tombstones of deleted organizations: consumers skip events for them (ADR-0031).
create table if not exists tombstones (org_id uuid primary key, deleted_at timestamptz not null default now());
