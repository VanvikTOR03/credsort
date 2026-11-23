-- One-off company fee to unlock lender identities for a loan request (covers the partner identity check).
alter table fee_rules drop constraint fee_rules_trigger_check;
alter table fee_rules add constraint fee_rules_trigger_check check (trigger in ('LOAN_FUNDED','OFFERS_UNLOCKED','MANUAL'));

create table unlock_payments (
    id uuid primary key,
    org_id uuid not null,
    application_id uuid not null unique,      -- one unlock per loan request: a retry returns the same payment
    amount numeric(19,4) not null check (amount >= 0),
    currency text not null default 'CHF' check (currency = 'CHF'),
    method text not null check (method in ('TWINT','VISA','MASTERCARD')),
    status text not null check (status in ('PAID')),
    provider text not null,
    provider_ref text not null,
    price_book_version int,
    created_at timestamptz not null default now()
);
alter table unlock_payments enable row level security;
alter table unlock_payments force row level security;
create policy tenant on unlock_payments using (org_id = app_org() or app_role() in ('SYSTEM','PLATFORM')) with check (org_id = app_org() or app_role() in ('SYSTEM','PLATFORM'));
