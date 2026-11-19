create table data_connections (
    id uuid primary key,
    org_id uuid not null,
    source_type text not null check (source_type in ('SYNTHETIC','BEXIO')),
    status text not null default 'ACTIVE' check (status in ('ACTIVE','REVOKED')),
    config jsonb not null default '{}'::jsonb,
    token_enc text,
    created_at timestamptz not null default now()
);
create table import_batches (
    id uuid primary key,
    org_id uuid not null,
    connection_id uuid not null references data_connections(id),
    source_type text not null,
    period_start date not null,
    period_end date not null,
    content_hash text not null,
    normalizer_version text not null,
    validator_version text not null,
    created_at timestamptz not null default now(),
    unique (connection_id, period_start, period_end, content_hash, normalizer_version)
);
create table import_jobs (
    id uuid primary key,
    org_id uuid not null,
    connection_id uuid not null references data_connections(id),
    status text not null default 'PENDING' check (status in ('PENDING','RUNNING','COMPLETED','FAILED')),
    progress int not null default 0,
    failure_reason text,
    attempts int not null default 0,
    locked_until timestamptz,
    batch_id uuid references import_batches(id),
    created_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz
);
-- at most one active job per connection (ADR-0010)
create unique index import_jobs_one_active on import_jobs (connection_id) where status in ('PENDING','RUNNING');
create table canonical_accounts (
    batch_id uuid not null references import_batches(id) on delete cascade,
    org_id uuid not null,
    code text not null,
    name text not null,
    primary key (batch_id, code)
);
create table opening_balances (
    batch_id uuid not null references import_batches(id) on delete cascade,
    org_id uuid not null,
    account_code text not null,
    amount numeric(19,4) not null,
    primary key (batch_id, account_code)
);
create table journal_entries (
    id bigserial primary key,
    batch_id uuid not null references import_batches(id) on delete cascade,
    org_id uuid not null,
    entry_date date not null,
    debit_account text not null,
    credit_account text not null,
    amount numeric(19,4) not null check (amount > 0),
    reference text not null
);
create index journal_entries_batch on journal_entries (batch_id);

do $$
declare t text;
begin
    foreach t in array array['data_connections','import_batches','import_jobs','canonical_accounts','opening_balances','journal_entries'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy tenant on %I using (org_id = app_org() or app_role() = ''SYSTEM'') with check (org_id = app_org() or app_role() = ''SYSTEM'')', t);
    end loop;
end $$;
