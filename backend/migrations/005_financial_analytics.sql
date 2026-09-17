begin;
create or replace function financial_summary(p_user_id uuid, p_month text)
returns table(
  month text, available_balance_cents bigint, income_cents bigint, expense_cents bigint,
  cash_expense_cents bigint, card_expense_cents bigint,
  receivable_provisions_cents bigint, payable_provisions_cents bigint,
  forecast_balance_cents bigint, bank_balance_cents bigint, investments_cents bigint,
  current_card_bills_cents bigint, estimated_net_worth_cents bigint
) language sql stable set search_path=public,pg_temp as $$
with bounds as (select (p_month||'-01')::date start),
v as (select
 coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_income_expense
   and transaction_type='income' and transaction_nature<>'credit_card_refund'),0)::bigint income,
 coalesce(sum(case when transaction_nature='credit_card_refund' then -amount_cents else amount_cents end)
   filter(where not is_provision and not excluded_from_category_analytics
   and (transaction_type='expense' or transaction_nature='credit_card_refund')),0)::bigint expense,
 coalesce(sum(amount_cents) filter(where not is_provision and not excluded_from_category_analytics
   and transaction_type='expense' and payment_method is distinct from 'card'),0)::bigint cash,
 coalesce(sum(case when transaction_nature='credit_card_refund' then -amount_cents else amount_cents end)
   filter(where not is_provision and transaction_nature in ('credit_card_purchase','credit_card_refund')),0)::bigint card,
 coalesce(sum(amount_cents) filter(where is_provision and transaction_type='income' and not excluded_from_income_expense),0)::bigint receivable,
 coalesce(sum(amount_cents) filter(where is_provision and transaction_type='expense' and not excluded_from_income_expense),0)::bigint payable
 from transactions,bounds where user_id=p_user_id and transaction_date>=bounds.start
 and transaction_date<bounds.start+interval '1 month'),
a as (select coalesce(sum(balance_cents) filter(where type='BANK'),0)::bigint bank,
 count(*) filter(where type='BANK') banks,
 coalesce(sum(balance_cents) filter(where type='INVESTMENT' and not exists
   (select 1 from investments i where i.pluggy_connection_id=financial_accounts.pluggy_connection_id)),0)::bigint invested
 from financial_accounts where user_id=p_user_id and currency='BRL'),
i as (select coalesce(sum(balance_cents),0)::bigint invested from investments
 where user_id=p_user_id and currency='BRL' and status is distinct from 'TOTAL_WITHDRAWAL'),
c as (select coalesce(sum(current_bill_cents),0)::bigint bills from credit_cards where user_id=p_user_id),
h as (select coalesce(sum(case when transaction_type='income' then amount_cents else -amount_cents end),0)::bigint balance
 from transactions,bounds where user_id=p_user_id and not is_provision
 and payment_method is distinct from 'card' and transaction_date<bounds.start+interval '1 month'
 and (not excluded_from_income_expense or is_card_bill_payment)),
b as (select case when p_month=to_char(current_date,'YYYY-MM') and a.banks>0 then a.bank else h.balance end available from a,h)
select p_month,b.available,v.income,v.expense,v.cash,v.card,v.receivable,v.payable,
b.available+v.receivable-v.payable,a.bank,a.invested+i.invested,c.bills,a.bank+a.invested+i.invested-c.bills
from v,a,i,c,b;
$$;

create or replace function top_categories(p_user_id uuid,p_month text)
returns table(category_id uuid,name text,icon text,amount_cents bigint)
language sql stable set search_path=public,pg_temp as $$
 select c.id,c.name::text,c.icon::text,
 sum(case when t.transaction_nature='credit_card_refund' then -t.amount_cents else t.amount_cents end)::bigint
 from transactions t join categories c on c.id=t.category_id
 where t.user_id=p_user_id and t.transaction_date >= (p_month||'-01')::date
 and t.transaction_date < (p_month||'-01')::date+interval '1 month'
 and not t.is_provision and not t.excluded_from_category_analytics
 and (t.transaction_type='expense' or t.transaction_nature='credit_card_refund')
 group by c.id order by 4 desc;
$$;
create or replace function financial_trend(p_user_id uuid,p_month text)
returns table(month text,income_cents bigint,expense_cents bigint,card_cents bigint,balance_cents bigint)
language sql stable set search_path=public,pg_temp as $$
 select s.month,s.income_cents,s.expense_cents,s.card_expense_cents,s.available_balance_cents
 from generate_series((p_month||'-01')::date-interval '3 months',
 (p_month||'-01')::date+interval '3 months',interval '1 month') m
 cross join lateral financial_summary(p_user_id,to_char(m,'YYYY-MM')) s;
$$;
create or replace function list_budgets(p_user_id uuid,p_month text)
returns table(id uuid,user_id uuid,name varchar,month date,limit_cents bigint,
 category_ids uuid[],spent_cents bigint,created_at timestamptz,updated_at timestamptz)
language sql stable set search_path=public,pg_temp as $$
 select b.id,b.user_id,b.name,b.month,b.limit_cents,
 array(select bc.category_id from budget_categories bc where bc.budget_id=b.id),
 coalesce((select sum(case when t.transaction_nature='credit_card_refund' then -t.amount_cents else t.amount_cents end)
 from transactions t where t.user_id=b.user_id
 and t.category_id in (select bc.category_id from budget_categories bc where bc.budget_id=b.id)
 and t.transaction_date>=b.month and t.transaction_date<b.month+interval '1 month'
 and not t.is_provision and not t.excluded_from_category_analytics
 and (t.transaction_type='expense' or t.transaction_nature='credit_card_refund')),0)::bigint,
 b.created_at,b.updated_at from budgets b where b.user_id=p_user_id and b.month=(p_month||'-01')::date;
$$;
commit;
