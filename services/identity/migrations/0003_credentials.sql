-- Local passwords (development and demo until Keycloak is connected, see ADR-0016 addendum). Only hashes are stored.
create table credentials (
    user_id uuid primary key references users(id) on delete cascade,
    password_hash text not null,
    failed_attempts int not null default 0,
    locked_until timestamptz,
    updated_at timestamptz not null default now()
);
-- Password hashes are readable only by the Identity service acting as the platform, never through a tenant context.
alter table credentials enable row level security;
alter table credentials force row level security;
create policy system_only on credentials for all using (app_role() = 'SYSTEM') with check (app_role() = 'SYSTEM');
