create table notifications (
    id uuid primary key,
    org_id uuid not null,
    kind text not null,
    title text not null,
    body text not null,
    link text,
    resource_ref uuid,                  -- the application/offer this is about (used to withdraw lender-facing messages on revocation)
    created_at timestamptz not null default now(),
    read_at timestamptz
);
create index notifications_org on notifications (org_id, created_at desc);
create index notifications_ref on notifications (resource_ref);
alter table notifications enable row level security;
alter table notifications force row level security;
create policy tenant on notifications using (org_id = app_org() or app_role() = 'SYSTEM') with check (org_id = app_org() or app_role() = 'SYSTEM');
