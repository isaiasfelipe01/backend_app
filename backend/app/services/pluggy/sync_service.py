from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from app.models.enums import AccountType
from app.repositories.protocols import FinanceRepository
from app.services.accounts import PluggyAccountService
from app.services.creditcards import PluggyCreditCardService
from app.services.pluggy.client import PluggyClient
from app.services.transactions import PluggyTransactionService
from app.services.transfers import CardPaymentMatcher, InternalTransferMatcher
from app.utils.logging import logger
from app.services.pluggy.normalizer import money_to_cents
from app.services.pluggy.investment_service import PluggyInvestmentService


@dataclass
class SyncCounters:
    institutions_total: int = 0
    institutions_succeeded: int = 0
    institutions_failed: int = 0
    accounts_updated: int = 0
    cards_updated: int = 0
    investments_updated: int = 0
    transactions_inserted: int = 0
    transactions_updated: int = 0
    transactions_unchanged: int = 0
    transfers_matched: int = 0
    card_payments_matched: int = 0
    errors: list[str] = field(default_factory=list)


class PluggySyncService:
    def __init__(self, client: PluggyClient, repository: FinanceRepository) -> None:
        self.client = client
        self.repository = repository
        self.accounts = PluggyAccountService(repository)
        self.cards = PluggyCreditCardService(repository)
        self.transactions = PluggyTransactionService(repository)
        self.transfer_matcher = InternalTransferMatcher()
        self.card_payment_matcher = CardPaymentMatcher()

    async def run(self, user_id: UUID, sync_id: UUID, item_ids: list[str] | None = None) -> None:
        counters = SyncCounters()
        try:
            connections = await self.repository.list_connections(user_id)
            if item_ids:
                allowed = set(item_ids)
                connections = [
                    connection for connection in connections if connection["item_id"] in allowed
                ]
            counters.institutions_total = len(connections)
            for connection in connections:
                try:
                    await self._sync_connection(user_id, sync_id, connection, counters)
                    counters.institutions_succeeded += 1
                except Exception as error:
                    counters.institutions_failed += 1
                    safe_error = (
                        f"{connection.get('institution_name') or connection['item_id']}: {error}"
                    )
                    counters.errors.append(safe_error[:500])
                    await self.repository.update_connection(
                        str(connection["id"]),
                        {
                            "sync_status": "error",
                            "last_sync_error": str(error)[:500],
                            "last_sync_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    logger.error(
                        "pluggy_connection_sync_failed",
                        sync_id=str(sync_id),
                        item_id=connection["item_id"],
                        error=str(error),
                    )
            if connections:
                await self._reconcile(user_id, counters)
            status = (
                "success"
                if not counters.institutions_failed
                else "partial"
                if counters.institutions_succeeded
                else "error"
            )
            await self.repository.finish_sync_run(sync_id, {"status": status, **asdict(counters)})
            logger.info(
                "pluggy_sync_finished", sync_id=str(sync_id), status=status, **asdict(counters)
            )
        except Exception as error:
            await self.repository.finish_sync_run(
                sync_id, {**asdict(counters), "status": "error", "errors": [str(error)[:500]]}
            )
            logger.error("pluggy_sync_failed", sync_id=str(sync_id), error=str(error))

    async def _sync_connection(
        self,
        user_id: UUID,
        sync_id: UUID,
        connection: dict[str, Any],
        counters: SyncCounters,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        await self.repository.update_connection(
            str(connection["id"]),
            {"sync_status": "running", "last_sync_at": now, "last_sync_error": None},
        )
        item = await self.client.get_item(connection["item_id"])
        accounts = await self.client.list_accounts(connection["item_id"])
        institution = (
            connection.get("institution_name")
            or (item.get("connector") or {}).get("name")
            or "Instituição"
        )
        account_count = card_count = investment_count = 0
        for account in accounts:
            financial_account, account_type, _ = await self.accounts.persist(
                user_id=user_id,
                connection=connection,
                account=account,
                institution_name=institution,
            )
            account_count += 1
            credit_card_id = None
            if account_type == AccountType.CREDIT:
                card, _ = await self.cards.persist(
                    user_id=user_id,
                    connection=connection,
                    financial_account=financial_account,
                    account=account,
                    institution_name=institution,
                )
                credit_card_id = str(card["id"])
                card_count += 1
            elif account_type == AccountType.INVESTMENT:
                investment_count += 1
            async for page in self.client.transaction_pages(str(account["id"])):
                result = await self.transactions.persist_page(
                    user_id=user_id,
                    connection=connection,
                    account=account,
                    financial_account=financial_account,
                    account_type=account_type,
                    credit_card_id=credit_card_id,
                    transactions=page,
                )
                counters.transactions_inserted += int(result.get("inserted", 0))
                counters.transactions_updated += int(result.get("updated", 0))
                counters.transactions_unchanged += int(result.get("unchanged", 0))
        counters.accounts_updated += account_count
        counters.cards_updated += card_count
        counters.investments_updated += investment_count
        investments = await self.client.list_investments(connection["item_id"])
        for investment in investments:
            result = await PluggyInvestmentService(self.client, self.repository).sync(
                user_id, connection, investment, institution
            )
            counters.transactions_inserted += result["inserted"]
            counters.transactions_updated += result["updated"]
            counters.transactions_unchanged += result["unchanged"]
            await self.repository.upsert_investment(
                {
                    "user_id": str(user_id),
                    "pluggy_connection_id": connection["id"],
                    "pluggy_investment_id": str(investment["id"]),
                    "name": investment.get("name") or "Investimento",
                    "institution_name": institution,
                    "type": investment.get("type"),
                    "currency": investment.get("currencyCode") or "BRL",
                    "balance_cents": money_to_cents(investment["balance"])
                    if investment.get("balance") is not None
                    else None,
                    "status": investment.get("status"),
                    "raw_payload": investment,
                    "last_synced_at": now,
                }
            )
        investment_count += len(investments)
        counters.investments_updated += len(investments)
        await self.repository.update_connection(
            str(connection["id"]),
            {
                "status": item.get("status") or connection.get("status") or "CONNECTED",
                "sync_status": "success",
                "last_sync_at": now,
                "last_successful_sync_at": datetime.now(UTC).isoformat(),
                "last_sync_error": None,
                "accounts_count": account_count,
                "cards_count": card_count,
                "investments_count": investment_count,
                "raw_payload": item,
            },
        )
        logger.info(
            "pluggy_connection_synced",
            sync_id=str(sync_id),
            item_id=connection["item_id"],
            accounts_found=len(accounts),
            accounts_updated=account_count,
        )

    async def _reconcile(self, user_id: UUID, counters: SyncCounters) -> None:
        records = await self.repository.reconciliation_candidates(user_id, date(1970, 1, 1))
        account_types = {
            account_id: AccountType(value)
            for account_id, value in (await self.repository.account_types(user_id)).items()
        }
        before = [dict(record) for record in records]
        counters.transfers_matched = self.transfer_matcher.match(records)
        counters.card_payments_matched = self.card_payment_matcher.match(records, account_types)
        changed = [record for old, record in zip(before, records) if old != record]
        if changed:
            await self.repository.update_reconciled_transactions(changed)
