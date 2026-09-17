begin;
create or replace function upsert_pluggy_transactions(p_transactions jsonb)
returns table(inserted integer,updated integer,unchanged integer)
language plpgsql security definer set search_path=public,pg_temp as $$
declare item jsonb; old transactions%rowtype; was_insert boolean;
 ni integer:=0; nu integer:=0; nn integer:=0;
begin
 for item in select value from jsonb_array_elements(p_transactions) loop
  if not exists(select 1 from financial_accounts a where a.id=(item->>'financial_account_id')::uuid
    and a.user_id=(item->>'user_id')::uuid and a.pluggy_connection_id=(item->>'pluggy_connection_id')::uuid
    and a.pluggy_account_id=item->>'pluggy_account_id') then
    raise exception 'Account ownership mismatch';
  end if;
  select * into old from transactions where user_id=(item->>'user_id')::uuid
    and pluggy_account_id=item->>'pluggy_account_id' and pluggy_transaction_id=item->>'pluggy_transaction_id';
  if found and old.is_internal_transfer and
    (old.amount_cents is distinct from (item->>'amount_cents')::bigint or
     old.transaction_date is distinct from (item->>'transaction_date')::date or
     old.transaction_type is distinct from (item->>'transaction_type')::transaction_type) then
    update transactions set is_internal_transfer=false,internal_transfer_group_id=null,
      transaction_nature='transfer',excluded_from_income_expense=false,excluded_from_category_analytics=false
      where user_id=old.user_id and internal_transfer_group_id=old.internal_transfer_group_id;
  end if;
  insert into transactions(user_id,source,pluggy_connection_id,pluggy_item_id,pluggy_account_id,
    pluggy_transaction_id,financial_account_id,credit_card_id,category_id,description,original_description,
    amount_cents,raw_amount_cents,transaction_type,transaction_nature,payment_method,transaction_date,
    is_provision,is_card_bill_payment,excluded_from_income_expense,excluded_from_category_analytics,
    raw_payload,pluggy_created_at,pluggy_updated_at,billing_period)
  values((item->>'user_id')::uuid,'pluggy',(item->>'pluggy_connection_id')::uuid,
    item->>'pluggy_item_id',item->>'pluggy_account_id',item->>'pluggy_transaction_id',
    (item->>'financial_account_id')::uuid,(item->>'credit_card_id')::uuid,(item->>'category_id')::uuid,
    left(item->>'description',240),left(item->>'original_description',240),
    (item->>'amount_cents')::bigint,(item->>'raw_amount_cents')::bigint,
    (item->>'transaction_type')::transaction_type,(item->>'transaction_nature')::transaction_nature,
    item->>'payment_method',(item->>'transaction_date')::date,
    coalesce((item->>'is_provision')::boolean,false),coalesce((item->>'is_card_bill_payment')::boolean,false),
    coalesce((item->>'excluded_from_income_expense')::boolean,false),
    coalesce((item->>'excluded_from_category_analytics')::boolean,false),
    coalesce(item->'raw_payload','{}'),(item->>'pluggy_created_at')::timestamptz,
    (item->>'pluggy_updated_at')::timestamptz,(item->>'billing_period')::date)
  on conflict(user_id,pluggy_account_id,pluggy_transaction_id) where source='pluggy'
  do update set
    description=case when transactions.user_edited_description then transactions.description else excluded.description end,
    original_description=excluded.original_description,
    category_id=case when transactions.user_edited_category then transactions.category_id else excluded.category_id end,
    amount_cents=excluded.amount_cents,raw_amount_cents=excluded.raw_amount_cents,
    transaction_date=excluded.transaction_date,transaction_type=excluded.transaction_type,
    transaction_nature=case when transactions.is_internal_transfer then transactions.transaction_nature else excluded.transaction_nature end,
    is_card_bill_payment=excluded.is_card_bill_payment,
    excluded_from_income_expense=transactions.is_internal_transfer or excluded.excluded_from_income_expense,
    excluded_from_category_analytics=transactions.is_internal_transfer or excluded.excluded_from_category_analytics,
    raw_payload=excluded.raw_payload,pluggy_created_at=excluded.pluggy_created_at,
    pluggy_updated_at=excluded.pluggy_updated_at,is_provision=excluded.is_provision,
    billing_period=excluded.billing_period,payment_method=excluded.payment_method
  where (transactions.raw_payload,transactions.amount_cents,transactions.transaction_date,
         transactions.original_description,transactions.pluggy_updated_at)
    is distinct from (excluded.raw_payload,excluded.amount_cents,excluded.transaction_date,
         excluded.original_description,excluded.pluggy_updated_at)
  returning xmax=0 into was_insert;
  if not found then nn:=nn+1; elsif was_insert then ni:=ni+1; else nu:=nu+1; end if;
 end loop;
 return query select ni,nu,nn;
end $$;
revoke all on function upsert_pluggy_transactions(jsonb) from public,anon,authenticated;
grant execute on function upsert_pluggy_transactions(jsonb) to service_role;
commit;
