-- Partner identity check, run once the company has paid the one-off unlock fee (Billing).
alter table organizations add column kyc_status text not null default 'NONE' check (kyc_status in ('NONE','VERIFIED','REJECTED'));
alter table organizations add column kyc_verified_at timestamptz;

-- Canton of the registered office, collected at sign-up.
alter table organizations add column canton text;
