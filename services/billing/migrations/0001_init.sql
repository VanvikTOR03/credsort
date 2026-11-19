create table price_books (
    id uuid primary key,
    version int not null unique,
    status text not null default 'DRAFT' check (status in ('DRAFT','ACTIVE','SUPERSEDED')),
    effective_from date,
    is_placeholder boolean not null default false,
    referral_percent numeric(6,2) not null default 20,
    created_at timestamptz not null default now(),
    activated_at timestamptz
);
create table fee_rules (
    id uuid primary key,
    price_book_id uuid not null references price_books(id),
    code text not null,
    payer text not null check (payer in ('SME','LENDER')),
    trigger text not null check (trigger in ('LOAN_FUNDED','MANUAL')),
    calculator text not null check (calculator in ('FIXED','PERCENT_OF_PRINCIPAL')),
    amount numeric(19,4),
    percent numeric(9,4),
    min_amount numeric(19,4),
    cap_amount numeric(19,4),
    currency text not null default 'CHF' check (currency = 'CHF'),
    tax_code text not null default 'TBD',
    unique (price_book_id, code),
    check ((calculator = 'FIXED' and amount is not null) or (calculator = 'PERCENT_OF_PRINCIPAL' and percent is not null))
);
-- Price books are immutable once active (ADR-0013): a price change is a NEW version, enforced by the database.
create function fee_rules_immutable() returns trigger language plpgsql as $$
begin
    if (select status from price_books where id = coalesce(old.price_book_id, new.price_book_id)) <> 'DRAFT' then
        raise exception 'fee rules of a non-draft price book are immutable';
    end if;
    return coalesce(new, old);
end $$;
create trigger fee_rules_immutable before update or delete on fee_rules for each row execute function fee_rules_immutable();

create table quotes (
    id uuid primary key,
    org_id uuid not null,
    payer_type text not null,
    action text not null,
    subject_id uuid not null,
    basis numeric(19,4) not null,
    amount numeric(19,4) not null,
    pricing text not null check (pricing in ('PRICED','UNPRICED')),
    price_book_version int,
    rule_codes text[] not null default '{}',
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);
create table fee_charges (
    id uuid primary key,
    org_id uuid not null,
    quote_id uuid not null unique references quotes(id),
    offer_id uuid not null,
    application_id uuid,
    basis numeric(19,4) not null,
    amount numeric(19,4) not null,
    price_book_version int,
    status text not null check (status in ('RECORDED','HELD','WAIVED','CANCELLED','NO_FEE')),
    payable_after timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create table referrals (org_id uuid primary key, referred_by_org_id uuid not null, created_at timestamptz not null default now());
create table referral_shares (
    id uuid primary key,
    charge_id uuid not null references fee_charges(id),
    org_id uuid not null,           -- the paying organization (RLS owner)
    fiduciary_org_id uuid not null,
    percent numeric(6,2) not null,
    amount numeric(19,4) not null
);
create table entitlement_overrides (org_id uuid primary key, entitlements text[] not null, updated_at timestamptz not null default now());
create table held_events (
    id uuid primary key,
    org_id uuid,
    source_event_id uuid not null,
    reason_code text not null,
    created_at timestamptz not null default now()
);

do $$
declare t text;
begin
    foreach t in array array['quotes','fee_charges','referrals','referral_shares','entitlement_overrides','held_events'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy tenant on %I using (org_id = app_org() or app_role() in (''SYSTEM'',''PLATFORM'')) with check (org_id = app_org() or app_role() in (''SYSTEM'',''PLATFORM''))', t);
    end loop;
    -- pricing is public to every authenticated organization (fee disclosure); only the platform writes it
    foreach t in array array['price_books','fee_rules'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy read_all on %I for select using (true)', t);
        execute format('create policy platform_write on %I for all using (app_role() in (''SYSTEM'',''PLATFORM'')) with check (app_role() in (''SYSTEM'',''PLATFORM''))', t);
    end loop;
end $$;
