import asyncio
from datetime import UTC, date, datetime
from typing import Any, Callable
from uuid import UUID

from supabase import Client


def _iso(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _iso(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_iso(item) for item in value]
    return value


class SupabaseRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    async def _run(self, operation: Callable[[], Any]) -> Any:
        return await asyncio.to_thread(operation)

    async def ensure_user(self, user_id: UUID) -> None:
        await self._run(
            lambda: self.client.rpc("ensure_app_user", {"p_user_id": str(user_id)}).execute()
        )

    async def list_connections(self, user_id: UUID) -> list[dict[str, Any]]:
        response = await self._run(
            lambda: self.client.table("pluggy_connection_overview")
            .select("*")
            .eq("user_id", str(user_id))
            .order("created_at")
            .execute()
        )
        return list(response.data or [])

    async def upsert_connection(
        self, user_id: UUID, item_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {"user_id": str(user_id), "item_id": item_id, **_iso(values)}
        response = await self._run(
            lambda: self.client.table("pluggy_connections")
            .upsert(payload, on_conflict="user_id,item_id")
            .execute()
        )
        return dict(response.data[0])

    async def update_connection(self, connection_id: str, values: dict[str, Any]) -> None:
        await self._run(
            lambda: self.client.table("pluggy_connections")
            .update(_iso(values))
            .eq("id", connection_id)
            .execute()
        )

    async def start_sync_run(self, user_id: UUID, sync_id: UUID) -> bool:
        try:
            await self._run(
                lambda: self.client.table("pluggy_sync_runs")
                .insert({"id": str(sync_id), "user_id": str(user_id), "status": "running"})
                .execute()
            )
            return True
        except Exception as error:
            # PostgreSQL partial unique index rejects concurrent runs. Do not hide
            # unrelated persistence failures.
            if "pluggy_sync_runs_one_active_per_user" in str(error) or "23505" in str(error):
                return False
            raise

    async def finish_sync_run(self, sync_id: UUID, values: dict[str, Any]) -> None:
        await self._run(
            lambda: self.client.table("pluggy_sync_runs")
            .update({**_iso(values), "finished_at": datetime.now(UTC).isoformat()})
            .eq("id", str(sync_id))
            .execute()
        )

    async def get_sync_run(self, user_id: UUID, sync_id: UUID) -> dict[str, Any] | None:
        response = await self._run(
            lambda: self.client.table("pluggy_sync_runs")
            .select("*")
            .eq("id", str(sync_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        return dict(response.data) if response.data else None

    async def upsert_financial_account(self, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        existing = await self._run(
            lambda: self.client.table("financial_accounts")
            .select("id,balance_cents,available_balance_cents,updated_at")
            .eq("user_id", str(values["user_id"]))
            .eq("pluggy_account_id", values["pluggy_account_id"])
            .maybe_single()
            .execute()
        )
        response = await self._run(
            lambda: self.client.table("financial_accounts")
            .upsert(_iso(values), on_conflict="user_id,pluggy_account_id")
            .execute()
        )
        return dict(response.data[0]), not bool(existing.data)

    async def upsert_credit_card(self, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        existing = await self._run(
            lambda: self.client.table("credit_cards")
            .select("id")
            .eq("user_id", str(values["user_id"]))
            .eq("pluggy_account_id", values["pluggy_account_id"])
            .maybe_single()
            .execute()
        )
        response = await self._run(
            lambda: self.client.table("credit_cards")
            .upsert(_iso(values), on_conflict="user_id,pluggy_account_id")
            .execute()
        )
        return dict(response.data[0]), not bool(existing.data)

    async def upsert_transaction_batch(self, records: list[dict[str, Any]]) -> dict[str, int]:
        if not records:
            return {"inserted": 0, "updated": 0, "unchanged": 0}
        response = await self._run(
            lambda: self.client.rpc(
                "upsert_pluggy_transactions", {"p_transactions": _iso(records)}
            ).execute()
        )
        rows = response.data or []
        return dict(rows[0] if isinstance(rows, list) and rows else rows)

    async def reconciliation_candidates(self, user_id: UUID, start: date) -> list[dict[str, Any]]:
        rows = await self.list_table("transactions", user_id, source="pluggy")
        return [
            r
            for r in rows
            if r["transaction_date"] >= start.isoformat()
            and r["transaction_nature"]
            in {"transfer", "investment_transfer", "card_bill_payment", "unknown"}
        ]

    async def update_reconciled_transactions(self, records: list[dict[str, Any]]) -> None:
        keys = {
            "transaction_nature",
            "is_internal_transfer",
            "internal_transfer_group_id",
            "is_card_bill_payment",
            "excluded_from_income_expense",
            "excluded_from_category_analytics",
        }
        for record in records:
            payload = {key: _iso(record[key]) for key in keys if key in record}
            await self._run(
                lambda record=record, payload=payload: self.client.table("transactions")
                .update(payload)
                .eq("id", record["id"])
                .execute()
            )

    async def account_types(self, user_id: UUID) -> dict[str, str]:
        response = await self._run(
            lambda: self.client.table("financial_accounts")
            .select("id,type")
            .eq("user_id", str(user_id))
            .execute()
        )
        return {str(row["id"]): str(row["type"]) for row in (response.data or [])}

    async def category_id(self, user_id: UUID, category_type: str, name: str) -> str:
        response = await self._run(
            lambda: self.client.table("categories")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("type", category_type)
            .eq("name", name)
            .maybe_single()
            .execute()
        )
        if response.data:
            return str(response.data["id"])
        fallback = await self._run(
            lambda: self.client.table("categories")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("type", category_type)
            .eq("name", "Outros")
            .single()
            .execute()
        )
        return str(fallback.data["id"])

    async def delete_connection(self, user_id: UUID, item_id: str) -> bool:
        response = await self._run(
            lambda: self.client.table("pluggy_connections")
            .delete()
            .eq("user_id", str(user_id))
            .eq("item_id", item_id)
            .execute()
        )
        return bool(response.data)

    async def register_webhook_event(self, values: dict[str, Any]) -> bool:
        try:
            await self._run(
                lambda: self.client.table("pluggy_webhook_events").insert(_iso(values)).execute()
            )
            return True
        except Exception as error:
            if "23505" in str(error) or "duplicate" in str(error).lower():
                response = await self._run(
                    lambda: self.client.table("pluggy_webhook_events")
                    .select("processing_status")
                    .eq("event_id", values["event_id"])
                    .single()
                    .execute()
                )
                return response.data["processing_status"] in {"pending", "error"}
            raise

    async def update_webhook_event(self, event_id: str, values: dict[str, Any]) -> None:
        await self._run(
            lambda: self.client.table("pluggy_webhook_events")
            .update(_iso(values))
            .eq("event_id", event_id)
            .execute()
        )

    async def list_table(self, table: str, user_id: UUID, **filters: Any) -> list[dict[str, Any]]:
        def operation() -> Any:
            query = self.client.table(table).select("*").eq("user_id", str(user_id))
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, _iso(value))
            return query.order("id")

        rows = []
        offset = 0
        while True:
            response = await self._run(lambda: operation().range(offset, offset + 499).execute())
            page = list(response.data or [])
            rows.extend(page)
            if len(page) < 500:
                return rows
            offset += 500

    async def insert_table(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._run(lambda: self.client.table(table).insert(_iso(payload)).execute())
        return dict(response.data[0])

    async def update_owned(
        self, table: str, resource_id: UUID, user_id: UUID, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = await self._run(
            lambda: self.client.table(table)
            .update(_iso(payload))
            .eq("id", str(resource_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        return dict(response.data[0]) if response.data else None

    async def delete_owned(self, table: str, resource_id: UUID, user_id: UUID) -> bool:
        response = await self._run(
            lambda: self.client.table(table)
            .delete()
            .eq("id", str(resource_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        return bool(response.data)

    async def call(self, function: str, params: dict[str, Any]) -> Any:
        if function == "list_transactions":
            rows = []
            offset = 0
            while True:
                response = await self._run(
                    lambda: self.client.rpc(function, _iso(params))
                    .range(offset, offset + 499)
                    .execute()
                )
                page = list(response.data or [])
                rows.extend(page)
                if len(page) < 500:
                    return rows
                offset += 500
        response = await self._run(lambda: self.client.rpc(function, _iso(params)).execute())
        return response.data

    async def upsert_investment(self, values: dict[str, Any]) -> None:
        await self._run(
            lambda: self.client.table("investments")
            .upsert(_iso(values), on_conflict="user_id,pluggy_investment_id")
            .execute()
        )
