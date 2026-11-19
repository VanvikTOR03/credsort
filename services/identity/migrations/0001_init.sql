create table organizations (
    id uuid primary key,
    type text not null check (type in ('SME','LENDER','FIDUCIARY','PLATFORM')),
    legal_name text not null,
    uid text,
    legal_form text,
    industry text,
    employees int,
    kyb_status text not null default 'UNVERIFIED' check (kyb_status in ('UNVERIFIED','PENDING','VERIFIED','REJECTED')),
    status text not null default 'ACTIVE' check (status in ('ACTIVE','SUSPENDED','DELETED')),
    referred_by_org_id uuid references organizations(id),
    referral_code text not null unique,
    created_at timestamptz not null default now()
);
create table users (
    id uuid primary key,
    keycloak_sub text unique,
    email text not null unique,
    display_name text not null,
    created_at timestamptz not null default now()
);
create table memberships (
    id uuid primary key,
    user_id uuid not null references users(id),
    org_id uuid not null references organizations(id),
    role text not null check (role in ('SME_ADMIN','SME_MEMBER','LENDER_ADMIN','CREDIT_OFFICER','FIDUCIARY_ADVISOR','PLATFORM_ADMIN')),
    created_at timestamptz not null default now(),
    revoked_at timestamptz,
    unique (user_id, org_id)
);
create table delegations (
    id uuid primary key,
    sme_org_id uuid not null references organizations(id),
    fiduciary_org_id uuid not null references organizations(id),
    scopes text[] not null,
    granted_by uuid references users(id),
    granted_at timestamptz not null default now(),
    revoked_at timestamptz
);
create unique index delegations_active on delegations (sme_org_id, fiduciary_org_id) where revoked_at is null;
create table deletion_requests (
    org_id uuid primary key,
    requested_at timestamptz not null default now(),
    confirmations jsonb not null default '{}'::jsonb,
    closed_at timestamptz
);

-- Row-level security (ADR-0017). SYSTEM = token issuance / onboarding code paths; PLATFORM = platform admin requests.
alter table organizations enable row level security;  alter table organizations force row level security;
create policy tenant on organizations
    using (id = app_org() or app_role() in ('SYSTEM','PLATFORM'))
    with check (id = app_org() or app_role() in ('SYSTEM','PLATFORM'));

alter table users enable row level security;  alter table users force row level security;
create policy member_view on users for select
    using (app_role() in ('SYSTEM','PLATFORM') or exists (select 1 from memberships m where m.user_id = users.id and m.org_id = app_org()));
create policy system_write on users for all using (app_role() = 'SYSTEM') with check (app_role() = 'SYSTEM');

alter table memberships enable row level security;  alter table memberships force row level security;
create policy tenant on memberships
    using (org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'))
    with check (org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'));

alter table delegations enable row level security;  alter table delegations force row level security;
create policy tenant on delegations
    using (sme_org_id = app_org() or fiduciary_org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'))
    with check (sme_org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'));

alter table deletion_requests enable row level security;  alter table deletion_requests force row level security;
create policy tenant on deletion_requests using (org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'))
    with check (app_role() in ('SYSTEM','PLATFORM') or org_id = app_org());
