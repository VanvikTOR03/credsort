-- Central activity log: append-only and hash-chained per organization stream (ADR-0028).
create table audit_streams (org_id uuid primary key, head_seq bigint not null default 0, head_hash text not null default '');
create table audit_log (
    id uuid primary key,
    org_id uuid not null,
    seq bigint not null,
    prev_hash text not null,
    hash text not null,
    source_service text not null,
    source_audit_id uuid not null unique,
    actor_user_id uuid,
    acting_org_id uuid,
    on_behalf_of_org_id uuid,
    action text not null,
    resource text not null,
    occurred_at timestamptz not null,
    unique (org_id, seq)
);
create index audit_log_org on audit_log (org_id, seq desc);
-- append-only: records are never updated except to pseudonymise personal references on deletion (those columns are not part of the hash)
create function audit_log_append_only() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then raise exception 'audit records cannot be deleted'; end if;
    if (old.id, old.org_id, old.seq, old.prev_hash, old.hash, old.source_service, old.source_audit_id, old.action, old.resource, old.occurred_at)
       is distinct from (new.id, new.org_id, new.seq, new.prev_hash, new.hash, new.source_service, new.source_audit_id, new.action, new.resource, new.occurred_at) then
        raise exception 'audit records are append-only';
    end if;
    return new;
end $$;
create trigger audit_log_append_only before update or delete on audit_log for each row execute function audit_log_append_only();
do $$
declare t text;
begin
    foreach t in array array['audit_streams','audit_log'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
        execute format('create policy tenant on %I using (org_id = app_org() or app_role() = ''SYSTEM'') with check (org_id = app_org() or app_role() = ''SYSTEM'')', t);
    end loop;
end $$;
