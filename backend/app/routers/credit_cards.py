from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import CreditCard, CreditCardCreate, CreditCardUpdate

router = APIRouter(prefix="/credit-cards", tags=["credit-cards"])


@router.get("", response_model=list[CreditCard])
async def list_credit_cards(repository: RepositoryDep, user_id: UserIdDep) -> list[dict]:
    return await repository.call("list_credit_cards", {"p_user_id": user_id}) or []


@router.post("", response_model=CreditCard, status_code=status.HTTP_201_CREATED)
async def create_credit_card(
    request: CreditCardCreate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    raise HTTPException(409, "Cartões são importados exclusivamente da Pluggy")


@router.put("/{card_id}", response_model=CreditCard)
async def update_credit_card(
    card_id: UUID, request: CreditCardUpdate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    raise HTTPException(409, "Dados de cartões são atualizados pela instituição")


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_card(card_id: UUID, repository: RepositoryDep, user_id: UserIdDep) -> None:
    cards = await repository.list_table("credit_cards", user_id, id=card_id)
    if not cards:
        raise HTTPException(404, "Cartão não encontrado")
    if cards[0]["origin"] == "PLUGGY":
        raise HTTPException(409, "Desconecte a instituição para remover este cartão")
    await repository.delete_owned("credit_cards", card_id, user_id)
