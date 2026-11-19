create table explanation_cache (
    org_id uuid not null,
    key text not null,
    body jsonb not null,
    created_at timestamptz not null default now(),
    primary key (org_id, key)
);
create table entitlements (org_id uuid primary key, entitlements text[] not null, updated_at timestamptz not null default now());
do $$
declare t text;
begin
    foreach t in array array['explanation_cache','entitlements'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy tenant on %I using (org_id = app_org() or app_role() = ''SYSTEM'') with check (org_id = app_org() or app_role() = ''SYSTEM'')', t);
    end loop;
end $$;
