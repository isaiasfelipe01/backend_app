begin;
alter table credit_cards add constraint cards_pluggy_only check(origin='PLUGGY' and pluggy_connection_id is not null);
create table investments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  pluggy_connection_id uuid not null references pluggy_connections(id) on delete cascade,
  pluggy_investment_id text not null,
  name text not null, institution_name text not null, type text,
  currency text not null default 'BRL', balance_cents bigint, status text,
  last_synced_at timestamptz, raw_payload jsonb not null default '{}',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(user_id,pluggy_investment_id)
);
create index investments_connection_idx on investments(pluggy_connection_id);
create index transactions_connection_idx on transactions(pluggy_connection_id);
create index transactions_card_idx on transactions(credit_card_id);
create index accounts_connection_idx on financial_accounts(pluggy_connection_id);
create index cards_connection_idx on credit_cards(pluggy_connection_id);
create index cards_account_idx on credit_cards(financial_account_id);
create index budget_categories_category_idx on budget_categories(category_id);
create unique index connections_item_owner_idx on pluggy_connections(item_id);
create trigger investments_updated_at before update on investments for each row execute function set_updated_at();
-- Personal API runs exclusively with service_role. Android has no database key.
do $$ declare t text; f record; begin
  foreach t in array array['users','categories','transactions','credit_cards','budgets',
    'budget_categories','pluggy_connections','financial_accounts','investments',
    'pluggy_sync_runs','pluggy_webhook_events'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon, authenticated',t);
    execute format('grant all on public.%I to service_role',t);
  end loop;
  for f in select p.oid::regprocedure signature from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' loop
    execute format('alter function %s set search_path = public, pg_temp',f.signature);
    execute format('revoke all on function %s from public, anon, authenticated',f.signature);
    execute format('grant execute on function %s to service_role',f.signature);
  end loop;
end $$;
alter view pluggy_connection_overview set (security_invoker=true);
revoke all on pluggy_connection_overview from anon, authenticated;
grant select on pluggy_connection_overview to service_role;
commit;
