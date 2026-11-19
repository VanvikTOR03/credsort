-- Reference data (immutable, versioned; ADR-0025). Not tenant data.
create table mapping_versions (id text primary key, rules jsonb not null, created_at timestamptz not null default now());
create table scorecard_versions (id text primary key, definition jsonb not null, created_at timestamptz not null default now());

create table snapshots (
    id uuid primary key,
    org_id uuid not null,
    batch_id uuid not null,
    mapping_version text not null references mapping_versions(id),
    source_type text not null,
    period_start date not null,
    period_end date not null,
    data jsonb not null,
    created_at timestamptz not null default now(),
    unique (batch_id, mapping_version)
);
create table metrics (
    id uuid primary key,
    org_id uuid not null,
    snapshot_id uuid not null references snapshots(id) on delete cascade,
    code text not null,
    value numeric(24,8),
    unit text not null,
    status text not null check (status in ('OK','UNAVAILABLE')),
    reason text,
    formula_version text not null,
    unique (snapshot_id, code)
);
create table assessments (
    id uuid primary key,
    org_id uuid not null,
    snapshot_id uuid not null references snapshots(id) on delete cascade,
    scorecard_version text not null references scorecard_versions(id),
    confidence_model_version text not null,
    as_of date not null,
    score int not null,
    category text not null check (category in ('A','B','C','D')),
    factors jsonb not null,
    confidence jsonb not null,
    created_at timestamptz not null default now(),
    unique (snapshot_id, scorecard_version, confidence_model_version, as_of)
);
create table scenarios (
    id uuid primary key,
    org_id uuid not null,
    assessment_id uuid not null references assessments(id) on delete cascade,
    inputs jsonb not null,
    result jsonb not null,
    created_at timestamptz not null default now()
);
create table pipeline_failures (
    id uuid primary key,
    org_id uuid not null,
    batch_id uuid not null,
    reason_code text not null,
    created_at timestamptz not null default now()
);
create table entitlements (
    org_id uuid primary key,
    entitlements text[] not null,
    updated_at timestamptz not null default now()
);

do $$
declare t text;
begin
    foreach t in array array['snapshots','metrics','assessments','scenarios','pipeline_failures','entitlements'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy tenant on %I using (org_id = app_org() or app_role() = ''SYSTEM'') with check (org_id = app_org() or app_role() = ''SYSTEM'')', t);
    end loop;
end $$;
