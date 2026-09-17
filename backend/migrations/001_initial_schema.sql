begin;

create extension if not exists pgcrypto;

create type category_type as enum ('income', 'expense');
create type transaction_type as enum ('income', 'expense');
create type transaction_nature as enum (
  'income', 'expense', 'credit_card_purchase', 'credit_card_refund',
  'card_bill_payment', 'transfer', 'internal_transfer', 'investment_transfer',
  'investment_income', 'adjustment', 'unknown'
);
create type transaction_source as enum ('manual', 'pluggy');
create type card_origin as enum ('MANUAL', 'PLUGGY');
create type sync_status as enum ('pending', 'running', 'success', 'partial', 'error');

create table users (
  id uuid primary key,
  email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  name varchar(60) not null,
  icon varchar(16) not null default '💰',
  type category_type not null,
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, type, name)
);

create table pluggy_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  item_id text not null,
  institution_name varchar(160),
  connector_id bigint,
  connector_image_url text,
  status varchar(40) not null default 'CONNECTED',
  sync_status sync_status not null default 'pending',
  accounts_count integer not null default 0,
  cards_count integer not null default 0,
  investments_count integer not null default 0,
  last_sync_at timestamptz,
  last_successful_sync_at timestamptz,
  last_external_update_at timestamptz,
  last_sync_error text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, item_id)
);

create table financial_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  pluggy_connection_id uuid not null references pluggy_connections(id) on delete cascade,
  pluggy_item_id text not null,
  pluggy_account_id text not null,
  institution_name varchar(160) not null,
  name varchar(160) not null,
  type varchar(30) not null check(type in ('BANK', 'CREDIT', 'INVESTMENT', 'OTHER')),
  subtype varchar(80),
  currency char(3) not null default 'BRL',
  balance_cents bigint not null default 0,
  available_balance_cents bigint,
  number_masked varchar(80),
  status varchar(40),
  last_synced_at timestamptz,
  last_transaction_date date,
  last_external_update_at timestamptz,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, pluggy_account_id)
);

create table credit_cards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  pluggy_connection_id uuid references pluggy_connections(id) on delete cascade,
  financial_account_id uuid references financial_accounts(id) on delete cascade,
  pluggy_account_id text,
  name varchar(100) not null,
  institution_name varchar(160),
  origin card_origin not null default 'MANUAL',
  limit_total_cents bigint check(limit_total_cents >= 0),
  limit_available_cents bigint,
  current_bill_cents bigint,
  closing_day smallint check(closing_day between 1 and 31),
  due_day smallint check(due_day between 1 and 31),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, pluggy_account_id)
);

create table transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  source transaction_source not null default 'pluggy' check(source = 'pluggy'),
  pluggy_connection_id uuid references pluggy_connections(id) on delete cascade,
  pluggy_item_id text,
  pluggy_account_id text,
  pluggy_transaction_id text,
  financial_account_id uuid references financial_accounts(id) on delete cascade,
  credit_card_id uuid references credit_cards(id) on delete set null,
  category_id uuid references categories(id) on delete set null,
  description varchar(240) not null default '',
  original_description varchar(240) not null default '',
  amount_cents bigint not null check(amount_cents >= 0),
  raw_amount_cents bigint not null,
  transaction_type transaction_type not null,
  transaction_nature transaction_nature not null,
  payment_method varchar(30),
  transaction_date date not null,
  billing_period date,
  is_provision boolean not null default false,
  is_internal_transfer boolean not null default false,
  is_card_bill_payment boolean not null default false,
  excluded_from_income_expense boolean not null default false,
  excluded_from_category_analytics boolean not null default false,
  internal_transfer_group_id uuid,
  user_edited_description boolean not null default false,
  user_edited_category boolean not null default false,
  installment_group_id uuid,
  installment_number integer,
  installment_count integer,
  recurrence_group_id uuid,
  raw_payload jsonb not null default '{}'::jsonb,
  pluggy_created_at timestamptz,
  pluggy_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check(pluggy_transaction_id is not null and pluggy_connection_id is not null and financial_account_id is not null)
);

create unique index transactions_pluggy_external_unique
  on transactions(user_id, pluggy_account_id, pluggy_transaction_id)
  where source = 'pluggy';

create table budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  name varchar(80) not null,
  month date not null check(extract(day from month) = 1),
  limit_cents bigint not null check(limit_cents > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, name, month)
);

create table budget_categories (
  budget_id uuid not null references budgets(id) on delete cascade,
  category_id uuid not null references categories(id) on delete cascade,
  primary key(budget_id, category_id)
);

create table pluggy_sync_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  status sync_status not null default 'pending',
  institutions_total integer not null default 0,
  institutions_succeeded integer not null default 0,
  institutions_failed integer not null default 0,
  accounts_updated integer not null default 0,
  cards_updated integer not null default 0,
  investments_updated integer not null default 0,
  transactions_inserted integer not null default 0,
  transactions_updated integer not null default 0,
  transactions_unchanged integer not null default 0,
  transfers_matched integer not null default 0,
  card_payments_matched integer not null default 0,
  errors jsonb not null default '[]'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create unique index pluggy_sync_runs_one_active_per_user
  on pluggy_sync_runs(user_id) where status in ('pending', 'running');

create table pluggy_webhook_events (
  id uuid primary key default gen_random_uuid(),
  event_id text not null unique,
  event_type varchar(100) not null,
  payload jsonb not null,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  processing_status varchar(30) not null default 'pending',
  error text
);

create index transactions_user_date_idx on transactions(user_id, transaction_date desc);
create index transactions_user_category_idx on transactions(user_id, category_id);
create index transactions_account_date_idx on transactions(financial_account_id, transaction_date desc);
create index transactions_pluggy_id_idx on transactions(pluggy_transaction_id);
create index financial_accounts_user_idx on financial_accounts(user_id);
create index financial_accounts_pluggy_idx on financial_accounts(pluggy_account_id);
create index pluggy_connections_user_idx on pluggy_connections(user_id);
create index budgets_user_month_idx on budgets(user_id, month);

create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

create trigger users_updated_at before update on users for each row execute function set_updated_at();
create trigger categories_updated_at before update on categories for each row execute function set_updated_at();
create trigger connections_updated_at before update on pluggy_connections for each row execute function set_updated_at();
create trigger accounts_updated_at before update on financial_accounts for each row execute function set_updated_at();
create trigger cards_updated_at before update on credit_cards for each row execute function set_updated_at();
create trigger transactions_updated_at before update on transactions for each row execute function set_updated_at();
create trigger budgets_updated_at before update on budgets for each row execute function set_updated_at();

create or replace function ensure_app_user(p_user_id uuid) returns void language plpgsql security definer as $$
begin
  insert into users(id) values(p_user_id) on conflict do nothing;
  insert into categories(user_id, name, icon, type, is_default) values
    (p_user_id, 'Alimentação', '🍽️', 'expense', true),
    (p_user_id, 'Transporte', '🚗', 'expense', true),
    (p_user_id, 'Moradia', '🏠', 'expense', true),
    (p_user_id, 'Saúde', '❤️', 'expense', true),
    (p_user_id, 'Lazer', '🎮', 'expense', true),
    (p_user_id, 'Educação', '📚', 'expense', true),
    (p_user_id, 'Vestuário', '👕', 'expense', true),
    (p_user_id, 'Supermercado', '🛒', 'expense', true),
    (p_user_id, 'Farmácia', '💊', 'expense', true),
    (p_user_id, 'Outros', '📦', 'expense', true),
    (p_user_id, 'Salário', '💼', 'income', true),
    (p_user_id, 'Freelance', '💻', 'income', true),
    (p_user_id, 'Investimentos', '📈', 'income', true),
    (p_user_id, 'Presentes', '🎁', 'income', true),
    (p_user_id, 'Outros', '💰', 'income', true)
  on conflict do nothing;
end $$;

create view pluggy_connection_overview as
select c.*,
  (select count(*) from financial_accounts a where a.pluggy_connection_id = c.id) as persisted_accounts_count
from pluggy_connections c;

commit;
