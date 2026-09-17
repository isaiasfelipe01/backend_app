from typing import Any


EXPENSE_MAPPING = {
    "FOOD": "Alimentação",
    "RESTAURANT": "Alimentação",
    "GROCERIES": "Supermercado",
    "SUPERMARKET": "Supermercado",
    "TRANSPORT": "Transporte",
    "MOBILITY": "Transporte",
    "HOME": "Moradia",
    "HOUSING": "Moradia",
    "HEALTH": "Saúde",
    "PHARMACY": "Farmácia",
    "ENTERTAINMENT": "Lazer",
    "EDUCATION": "Educação",
    "CLOTHING": "Vestuário",
}
INCOME_MAPPING = {
    "SALARY": "Salário",
    "FREELANCE": "Freelance",
    "INVESTMENT": "Investimentos",
    "DIVIDEND": "Investimentos",
    "GIFT": "Presentes",
}


def map_pluggy_category(payload: dict[str, Any], transaction_type: str) -> str:
    raw = payload.get("category")
    if isinstance(raw, dict):
        raw = raw.get("name") or raw.get("id")
    value = str(raw or "").upper()
    mapping = INCOME_MAPPING if transaction_type == "income" else EXPENSE_MAPPING
    for marker, local in mapping.items():
        if marker in value:
            return local
    return "Outros"
