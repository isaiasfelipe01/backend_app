begin;

create or replace function upsert_pluggy_transactions(p_transactions jsonb)
returns table(inserted integer, updated integer, unchanged integer)
language plpgsql security definer as $$
declare
  item jsonb;
  previous transactions%rowtype;
  inserted_count integer := 0;
  updated_count integer := 0;
  unchanged_count integer := 0;
begin
  for item in select value from jsonb_array_elements(p_transactions)
  loop
    select * into previous from transactions
      where user_id = (item->>'user_id')::uuid
        and pluggy_account_id = item->>'pluggy_account_id'
        and pluggy_transaction_id = item->>'pluggy_transaction_id';

    if not found then
      insert into transactions(
        user_id, source, pluggy_connection_id, pluggy_item_id, pluggy_account_id,
        pluggy_transaction_id, financial_account_id, credit_card_id, category_id,
        description, original_description, amount_cents, raw_amount_cents,
        transaction_type, transaction_nature, payment_method, transaction_date,
        is_provision, is_internal_transfer, is_card_bill_payment,
        excluded_from_income_expense, excluded_from_category_analytics,
        raw_payload, pluggy_created_at, pluggy_updated_at
      ) values (
        (item->>'user_id')::uuid, 'pluggy', (item->>'pluggy_connection_id')::uuid,
        item->>'pluggy_item_id', item->>'pluggy_account_id', item->>'pluggy_transaction_id',
        (item->>'financial_account_id')::uuid, nullif(item->>'credit_card_id','')::uuid,
        nullif(item->>'category_id','')::uuid, item->>'description', item->>'original_description',
        (item->>'amount_cents')::bigint, (item->>'raw_amount_cents')::bigint,
        (item->>'transaction_type')::transaction_type,
        (item->>'transaction_nature')::transaction_nature, item->>'payment_method',
        (item->>'transaction_date')::date, coalesce((item->>'is_provision')::boolean, false),
        coalesce((item->>'is_internal_transfer')::boolean, false),
        coalesce((item->>'is_card_bill_payment')::boolean, false),
        coalesce((item->>'excluded_from_income_expense')::boolean, false),
        coalesce((item->>'excluded_from_category_analytics')::boolean, false),
        coalesce(item->'raw_payload', '{}'::jsonb), nullif(item->>'pluggy_created_at','')::timestamptz,
        nullif(item->>'pluggy_updated_at','')::timestamptz
      );
      inserted_count := inserted_count + 1;
    elsif previous.raw_payload is distinct from coalesce(item->'raw_payload', '{}'::jsonb)
       or previous.raw_amount_cents is distinct from (item->>'raw_amount_cents')::bigint
       or previous.transaction_date is distinct from (item->>'transaction_date')::date
       or previous.original_description is distinct from item->>'original_description' then
      update transactions set
        original_description = item->>'original_description',
        description = case when user_edited_description then description else item->>'description' end,
        category_id = case when user_edited_category then category_id else nullif(item->>'category_id','')::uuid end,
        amount_cents = (item->>'amount_cents')::bigint,
        raw_amount_cents = (item->>'raw_amount_cents')::bigint,
        transaction_type = (item->>'transaction_type')::transaction_type,
        transaction_nature = case when is_internal_transfer then transaction_nature else (item->>'transaction_nature')::transaction_nature end,
        payment_method = item->>'payment_method', transaction_date = (item->>'transaction_date')::date,
        credit_card_id = nullif(item->>'credit_card_id','')::uuid,
        raw_payload = coalesce(item->'raw_payload', '{}'::jsonb),
        pluggy_created_at = nullif(item->>'pluggy_created_at','')::timestamptz,
        pluggy_updated_at = nullif(item->>'pluggy_updated_at','')::timestamptz
      where id = previous.id;
      updated_count := updated_count + 1;
    else
      unchanged_count := unchanged_count + 1;
    end if;
  end loop;
  return query select inserted_count, updated_count, unchanged_count;
end $$;

commit;
