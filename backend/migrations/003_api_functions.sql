begin;

create or replace function delete_custom_category(p_user_id uuid, p_category_id uuid)
returns boolean language plpgsql security definer as $$
declare
  target categories%rowtype;
  fallback_id uuid;
begin
  select * into target from categories where id = p_category_id and user_id = p_user_id;
  if not found or target.is_default then return false; end if;
  perform ensure_app_user(p_user_id);
  select id into fallback_id from categories
    where user_id = p_user_id and type = target.type and name = 'Outros' and is_default limit 1;
  update transactions set category_id = fallback_id where category_id = target.id;
  delete from categories where id = target.id;
  return true;
end $$;

create or replace function list_transactions(
  p_user_id uuid, p_month text default null, p_search text default null,
  p_category_id uuid default null, p_credit_card_id uuid default null,
  p_financial_account_id uuid default null
) returns setof transactions language sql stable as $$
  select * from transactions t
  where t.user_id = p_user_id
    and (p_month is null or to_char(t.transaction_date, 'YYYY-MM') = p_month)
    and (p_search is null or t.description ilike '%' || p_search || '%')
    and (p_category_id is null or t.category_id = p_category_id)
    and (p_credit_card_id is null or t.credit_card_id = p_credit_card_id)
    and (p_financial_account_id is null or t.financial_account_id = p_financial_account_id)
  order by t.transaction_date desc, t.created_at desc;
$$;

create or replace function list_credit_cards(p_user_id uuid)
returns setof credit_cards language sql stable as $$
  select c.* from credit_cards c where c.user_id = p_user_id order by c.created_at;
$$;

create or replace function upsert_budget(
  p_user_id uuid, p_name text, p_month date, p_limit_cents bigint, p_category_ids uuid[]
) returns setof budgets language plpgsql security definer as $$
declare target budgets%rowtype;
begin
  if array_length(p_category_ids, 1) is null or exists(
    select 1 from unnest(p_category_ids) id left join categories c on c.id=id
    where c.id is null or c.user_id <> p_user_id or c.type <> 'expense'
  ) then return; end if;
  insert into budgets(user_id, name, month, limit_cents)
    values(p_user_id, p_name, p_month, p_limit_cents)
    on conflict(user_id, name, month) do update set limit_cents=excluded.limit_cents
    returning * into target;
  delete from budget_categories where budget_id=target.id;
  insert into budget_categories(budget_id, category_id)
    select target.id, id from unnest(p_category_ids) id;
  return next target;
end $$;

create or replace function list_budgets(p_user_id uuid, p_month text)
returns table(
  id uuid, user_id uuid, name varchar, month date, limit_cents bigint,
  category_ids uuid[], spent_cents bigint, created_at timestamptz, updated_at timestamptz
) language sql stable as $$
  select b.id, b.user_id, b.name, b.month, b.limit_cents,
    array(select bc.category_id from budget_categories bc where bc.budget_id=b.id),
    coalesce((select sum(t.amount_cents) from transactions t
      where t.user_id=b.user_id and t.category_id in (select bc.category_id from budget_categories bc where bc.budget_id=b.id)
        and to_char(t.transaction_date,'YYYY-MM')=p_month and not t.is_provision
        and not t.excluded_from_category_analytics and t.transaction_type='expense'),0)::bigint,
    b.created_at, b.updated_at
  from budgets b
  where b.user_id=p_user_id and to_char(b.month,'YYYY-MM')=p_month
  ;
$$;

create or replace function financial_summary(p_user_id uuid, p_month text)
returns table(
  month text, available_balance_cents bigint, income_cents bigint, expense_cents bigint,
  cash_expense_cents bigint, card_expense_cents bigint,
  receivable_provisions_cents bigint, payable_provisions_cents bigint,
  forecast_balance_cents bigint, bank_balance_cents bigint, investments_cents bigint,
  current_card_bills_cents bigint, estimated_net_worth_cents bigint
) language sql stable as $$
with values_for_month as (
  select
    coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_income_expense and transaction_type='income'),0)::bigint income,
    coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_income_expense and transaction_type='expense'),0)::bigint expense,
    coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_income_expense and transaction_type='expense' and payment_method <> 'card'),0)::bigint cash_expense,
    coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_income_expense and transaction_nature='credit_card_purchase'),0)::bigint card_expense,
    coalesce(sum(amount_cents) filter(where is_provision and transaction_type='income'),0)::bigint receivable,
    coalesce(sum(amount_cents) filter(where is_provision and transaction_type='expense'),0)::bigint payable
  from transactions where user_id=p_user_id and to_char(transaction_date,'YYYY-MM')=p_month
), assets as (
  select
    coalesce(sum(balance_cents) filter(where type='BANK'),0)::bigint bank,
    coalesce(sum(balance_cents) filter(where type='INVESTMENT'),0)::bigint invested
  from financial_accounts where user_id=p_user_id
), cards as (
  select coalesce(sum(current_bill_cents),0)::bigint bills from credit_cards where user_id=p_user_id
), historical as (
  select coalesce(sum(case when transaction_type='income' then amount_cents else -amount_cents end),0)::bigint balance
  from transactions where user_id=p_user_id and not is_provision and not excluded_from_income_expense
    and transaction_date < (to_date(p_month||'-01','YYYY-MM-DD') + interval '1 month')::date
    and payment_method <> 'card'
)
select p_month,
  case when p_month=to_char(current_date,'YYYY-MM') and assets.bank<>0 then assets.bank else historical.balance end,
  v.income, v.expense, v.cash_expense, v.card_expense, v.receivable, v.payable,
  (case when p_month=to_char(current_date,'YYYY-MM') and assets.bank<>0 then assets.bank else historical.balance end)+v.receivable-v.payable,
  assets.bank, assets.invested, cards.bills, assets.bank+assets.invested-cards.bills
from values_for_month v cross join assets cross join cards cross join historical;
$$;

create or replace function top_categories(p_user_id uuid, p_month text)
returns table(category_id uuid, name text, icon text, amount_cents bigint) language sql stable as $$
  select c.id, c.name::text, c.icon::text, sum(t.amount_cents)::bigint
  from transactions t join categories c on c.id=t.category_id
  where t.user_id=p_user_id and to_char(t.transaction_date,'YYYY-MM')=p_month
    and t.transaction_type='expense' and not t.is_provision and not t.excluded_from_category_analytics
  group by c.id order by sum(t.amount_cents) desc limit 10;
$$;

create or replace function financial_trend(p_user_id uuid, p_month text)
returns table(month text, income_cents bigint, expense_cents bigint, card_cents bigint, balance_cents bigint)
language sql stable as $$
with months as (
  select generate_series(to_date(p_month||'-01','YYYY-MM-DD')-interval '3 months',
    to_date(p_month||'-01','YYYY-MM-DD')+interval '3 months', interval '1 month')::date m
)
select to_char(m.m,'YYYY-MM'),
  coalesce(sum(t.amount_cents) filter(where t.transaction_type='income' and not t.excluded_from_income_expense),0)::bigint,
  coalesce(sum(t.amount_cents) filter(where t.transaction_type='expense' and not t.excluded_from_income_expense),0)::bigint,
  coalesce(sum(t.amount_cents) filter(where t.transaction_nature='credit_card_purchase'),0)::bigint,
  coalesce(sum(case when t.transaction_type='income' then t.amount_cents else -t.amount_cents end)
    filter(where not t.excluded_from_income_expense),0)::bigint
from months m left join transactions t on t.user_id=p_user_id and date_trunc('month',t.transaction_date)=m.m
  and not t.is_provision group by m.m order by m.m;
$$;

create or replace function connection_owner(p_item_id text)
returns table(user_id uuid, id uuid) language sql stable security definer as $$
  select c.user_id,c.id from pluggy_connections c where c.item_id=p_item_id limit 1;
$$;

commit;
