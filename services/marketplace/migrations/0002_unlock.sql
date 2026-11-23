-- A company unlocks the identities of the lenders that made offers by paying a one-off fee (Billing). Until then offers are shown without names.
alter table applications add column unlocked_at timestamptz;
