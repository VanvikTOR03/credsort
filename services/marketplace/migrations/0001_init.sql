create table applications (
    id uuid primary key,
    sme_org_id uuid not null,
    status text not null default 'DRAFT' check (status in ('DRAFT','PUBLISHED','OFFER_SELECTED','FUNDED','CANCELLED','WITHDRAWN')),
    amount numeric(19,4) not null check (amount > 0),
    term_months int not null check (term_months between 1 and 360),
    purpose text,
    collateral text,
    assessment_id uuid,
    industry text,
    employees int,
    published_profile_id uuid,
    selected_offer_id uuid,
    created_at timestamptz not null default now(),
    published_at timestamptz,
    selected_at timestamptz,
    funded_at timestamptz,
    dispute_until timestamptz,
    disputed_at timestamptz,
    closed_at timestamptz
);
-- The frozen copy of exactly the fields the SME consented to (ADR-0026). Immutable.
create table published_profiles (
    id uuid primary key,
    application_id uuid not null references applications(id) on delete cascade,
    sme_org_id uuid not null,
    assessment_id uuid not null,
    version int not null default 1,
    fields jsonb not null,
    as_of date not null,
    created_at timestamptz not null default now()
);
create function published_profiles_frozen() returns trigger language plpgsql as $$
begin raise exception 'published profiles are immutable'; end $$;
create trigger published_profiles_frozen before update on published_profiles for each row execute function published_profiles_frozen();

create table disclosures (
    id uuid primary key,
    application_id uuid not null references applications(id) on delete cascade,
    sme_org_id uuid not null,
    lender_org_id uuid,                       -- null = every verified lender
    level text not null check (level in ('summary','full')),
    purpose text not null check (purpose in ('matching','application_review')),
    permitted_fields text[] not null,
    profile_id uuid not null references published_profiles(id) on delete cascade,
    granted_at timestamptz not null default now(),
    revoked_at timestamptz
);
create index disclosures_app on disclosures (application_id) where revoked_at is null;
create table access_requests (
    id uuid primary key,
    application_id uuid not null references applications(id) on delete cascade,
    sme_org_id uuid not null,
    lender_org_id uuid not null,
    requested_fields text[] not null,
    status text not null default 'PENDING' check (status in ('PENDING','APPROVED','DENIED')),
    created_at timestamptz not null default now(),
    decided_at timestamptz
);
create unique index access_requests_pending on access_requests (application_id, lender_org_id) where status = 'PENDING';
create table lender_preferences (
    id uuid primary key,
    lender_org_id uuid not null,
    version int not null,
    criteria jsonb not null,
    created_at timestamptz not null default now(),
    unique (lender_org_id, version)
);
create table offers (
    id uuid primary key,
    application_id uuid not null references applications(id) on delete cascade,
    sme_org_id uuid not null,
    lender_org_id uuid not null,
    lender_name text not null,
    status text not null default 'SUBMITTED' check (status in ('SUBMITTED','SELECTED','REJECTED','WITHDRAWN','EXPIRED','FUNDED','CANCELLED')),
    amount numeric(19,4) not null check (amount > 0),
    rate numeric(7,4) not null check (rate >= 0 and rate <= 30),
    term_months int not null check (term_months between 1 and 360),
    fees numeric(19,4) not null default 0 check (fees >= 0),
    repayment text not null check (repayment in ('BULLET','LINEAR','ANNUITY')),
    collateral text,
    valid_until date not null,
    sme_quote_id uuid, sme_quote_token text, sme_fee_amount numeric(19,4), sme_fee_pricing text,
    lender_quote_id uuid, lender_quote_token text, lender_fee_amount numeric(19,4), lender_fee_pricing text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
-- exactly one selected offer per application, guaranteed by the database (ADR-0011)
create unique index one_selected_offer on offers (application_id) where status in ('SELECTED','FUNDED');
create unique index one_open_offer_per_lender on offers (application_id, lender_org_id) where status = 'SUBMITTED';
-- offer terms are immutable after submission: changed terms mean a new offer (ADR-0011)
create function offer_terms_immutable() returns trigger language plpgsql as $$
begin
    if (old.amount, old.rate, old.term_months, old.fees, old.repayment, old.collateral, old.valid_until, old.lender_org_id, old.application_id, old.sme_quote_id, old.lender_quote_id)
       is distinct from (new.amount, new.rate, new.term_months, new.fees, new.repayment, new.collateral, new.valid_until, new.lender_org_id, new.application_id, new.sme_quote_id, new.lender_quote_id) then
        raise exception 'offer terms are immutable';
    end if;
    new.updated_at = now();
    return new;
end $$;
create trigger offer_terms_immutable before update on offers for each row execute function offer_terms_immutable();

-- Anonymized observations for the rate benchmark (ADR-0022): no organization ids, only a lender key to count distinct lenders.
create table benchmark_observations (
    id uuid primary key,
    category text,
    amount_band text not null,
    term_months int not null,
    rate numeric(7,4) not null,
    lender_key text not null,
    observed_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- row-level security (ADR-0008, ADR-0017)
-- Roles set by the service per request: SME (the SME or a delegate), LENDER, SYSTEM (consumers), EVENT (consumers for one org).
do $$
declare t text;
begin
    foreach t in array array['applications','published_profiles','disclosures','access_requests','lender_preferences','offers','benchmark_observations'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
    end loop;
end $$;

create policy owner on applications using (sme_org_id = app_org() or app_role() = 'SYSTEM') with check (sme_org_id = app_org() or app_role() = 'SYSTEM');
-- A lender sees an application ONLY while a current disclosure to it exists (published + consented).
create policy lender_read on applications for select using (
    app_role() = 'LENDER' and status in ('PUBLISHED','OFFER_SELECTED','FUNDED') and exists (
        select 1 from disclosures d where d.application_id = applications.id and d.revoked_at is null
          and (d.lender_org_id is null or d.lender_org_id = app_org())));

create policy owner on published_profiles using (sme_org_id = app_org() or app_role() = 'SYSTEM') with check (sme_org_id = app_org() or app_role() = 'SYSTEM');
create policy lender_read on published_profiles for select using (
    app_role() = 'LENDER' and exists (
        select 1 from disclosures d where d.profile_id = published_profiles.id and d.revoked_at is null
          and (d.lender_org_id is null or d.lender_org_id = app_org())));

create policy owner on disclosures using (sme_org_id = app_org() or app_role() = 'SYSTEM') with check (sme_org_id = app_org() or app_role() = 'SYSTEM');
create policy lender_read on disclosures for select using (
    app_role() = 'LENDER' and revoked_at is null and (lender_org_id is null or lender_org_id = app_org()));

create policy parties on access_requests using (sme_org_id = app_org() or lender_org_id = app_org() or app_role() = 'SYSTEM')
    with check (sme_org_id = app_org() or lender_org_id = app_org() or app_role() = 'SYSTEM');
create policy owner on lender_preferences using (lender_org_id = app_org() or app_role() = 'SYSTEM') with check (lender_org_id = app_org() or app_role() = 'SYSTEM');
create policy parties on offers using (sme_org_id = app_org() or lender_org_id = app_org() or app_role() = 'SYSTEM')
    with check (sme_org_id = app_org() or lender_org_id = app_org() or app_role() = 'SYSTEM');
create policy write_only on benchmark_observations for insert with check (true);
create policy system_all on benchmark_observations for all using (app_role() = 'SYSTEM') with check (app_role() = 'SYSTEM');  -- retention jobs may also delete
