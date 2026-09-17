from datetime import date
from app.services.transactions.manual_service import add_months


def next_month_plan(month: str, transactions: list[dict], cards: list[dict]) -> dict:
    next_month = add_months(date.fromisoformat(month + '-01'), 1).strftime('%Y-%m')
    provisions = other = 0
    card_consumption: dict[str, int] = {}
    for row in transactions:
        if row.get('excluded_from_category_analytics'):
            continue
        signed = -row['amount_cents'] if row['transaction_nature']=='credit_card_refund' else row['amount_cents']
        if row.get('payment_method')=='card':
            if str(row.get('billing_period') or '')[:7]==next_month:
                card_id=row.get('credit_card_id')
                card_consumption[card_id]=card_consumption.get(card_id,0)+signed
        elif str(row['transaction_date'])[:7]==next_month and row['transaction_type']=='expense':
            if row.get('is_provision'):
                provisions += signed
            else:
                other += signed
    bill_total = 0
    for card in cards:
        raw = card.get('raw_payload') or {}
        due = str((raw.get('creditData') or {}).get('balanceDueDate') or '')[:7]
        bill_total += card['current_bill_cents'] if due==next_month and card.get('current_bill_cents') is not None else card_consumption.get(card['id'],0)
    return {'month':next_month,'cash_provisions_cents':provisions,'card_bills_cents':bill_total,
            'other_expenses_cents':other,'total_cents':provisions+bill_total+other}
