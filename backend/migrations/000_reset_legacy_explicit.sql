-- DESTRUCTIVE, opt-in only. Authorized for the inspected legacy MeuFinanças project.
-- Never execute as part of ordinary startup or synchronization.
-- Execute atomically with 001..004 when replacing the legacy schema.
drop table if exists public.transactions, public.financial_accounts,
  public.credit_cards, public.budgets, public.categories,
  public.pluggy_webhook_events, public.pluggy_connections, public.users;
