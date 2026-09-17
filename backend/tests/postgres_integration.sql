-- Isolated verification against the real PostgreSQL functions. All data rolls back.
begin;
do $$
declare
 u uuid:=gen_random_uuid(); c uuid; a uuid; cat uuid; payload jsonb; result record; total record;
begin
 perform ensure_app_user(u);
 if (select count(*) from categories where user_id=u) <> 15 then raise exception 'category seed'; end if;
 insert into pluggy_connections(user_id,item_id,institution_name) values(u,'test-'||u,'Test') returning id into c;
 insert into financial_accounts(user_id,pluggy_connection_id,pluggy_item_id,pluggy_account_id,institution_name,name,type,balance_cents)
 values(u,c,'test-'||u,'account-'||u,'Test','Test','BANK',0) returning id into a;
 select id into cat from categories where user_id=u and name='Outros' and type='expense';
 select jsonb_agg(jsonb_build_object('user_id',u,'pluggy_connection_id',c,'pluggy_item_id','test-'||u,
 'pluggy_account_id','account-'||u,'pluggy_transaction_id','tx-'||n,'financial_account_id',a,
 'category_id',cat,'description','Purchase','original_description','Purchase','amount_cents',100,
 'raw_amount_cents',-100,'transaction_type','expense','transaction_nature','expense',
 'payment_method','cash','transaction_date',current_date,'raw_payload',jsonb_build_object('id','tx-'||n,'amount',-1)))
 into payload from generate_series(1,100) n;
 select * into result from upsert_pluggy_transactions(payload);
 if result.inserted<>100 then raise exception 'first sync inserts %',result; end if;
 select * into result from upsert_pluggy_transactions(payload);
 if result.inserted<>0 or result.updated<>0 or result.unchanged<>100 then raise exception 'repeat %',result; end if;
 select * into total from financial_summary(u,to_char(current_date,'YYYY-MM'));
 if total.expense_cents<>10000 or total.available_balance_cents<>0 then raise exception 'summary %',total; end if;
 select jsonb_agg((payload->0)||jsonb_build_object('pluggy_transaction_id','new-'||n,'raw_payload',jsonb_build_object('id','new-'||n)))
 into payload from generate_series(1,3) n;
 select * into result from upsert_pluggy_transactions(payload);
 if result.inserted<>3 then raise exception 'incremental inserts %',result; end if;
 update transactions set description='Local edit',user_edited_description=true,user_edited_category=true
 where user_id=u and pluggy_transaction_id='tx-1';
 payload:=jsonb_build_array((payload->0)||jsonb_build_object('pluggy_transaction_id','tx-1','description','Changed externally','original_description','Changed externally','raw_payload','{"id":"tx-1","amount":-2}'::jsonb,'amount_cents',200,'raw_amount_cents',-200));
 select * into result from upsert_pluggy_transactions(payload);
 if result.updated<>1 then raise exception 'external update %',result; end if;
 if (select description from transactions where user_id=u and pluggy_transaction_id='tx-1')<>'Local edit' then raise exception 'local edit lost'; end if;
 if exists(select 1 from transactions where user_id=u and category_id<>cat) then raise exception 'category lost'; end if;
 delete from pluggy_connections where id=c;
 if exists(select 1 from transactions where user_id=u) then raise exception 'disconnect cascade'; end if;
 if (select count(*) from categories where user_id=u)<>15 then raise exception 'categories deleted'; end if;
end $$;
rollback;
select 'PostgreSQL integration passed; all fixtures rolled back' as verification;
