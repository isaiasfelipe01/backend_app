import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator

import httpx

from app.config import Settings


class PluggyError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PluggyClient:
    """Small typed boundary around documented Pluggy endpoints.

    It never logs request headers or credentials. Transaction pagination follows
    the `cursor` returned by Pluggy until it is absent.
    """

    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.pluggy_base_url,
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )
        self._api_key: str | None = None
        self._api_key_expires_at: datetime | None = None
        self._auth_lock = asyncio.Lock()

    async def __aenter__(self) -> "PluggyClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _authenticate(self) -> str:
        now = datetime.now(UTC)
        if self._api_key and self._api_key_expires_at and now < self._api_key_expires_at:
            return self._api_key
        async with self._auth_lock:
            now = datetime.now(UTC)
            if self._api_key and self._api_key_expires_at and now < self._api_key_expires_at:
                return self._api_key
            if not self._settings.pluggy_configured:
                raise PluggyError("Credenciais Pluggy não configuradas")
            response = await self._client.post(
                "/auth",
                json={
                    "clientId": self._settings.pluggy_client_id,
                    "clientSecret": self._settings.pluggy_client_secret.get_secret_value(),
                },
                headers={"accept": "application/json"},
            )
            self._raise_for_status(response, "autenticar")
            api_key = response.json().get("apiKey")
            if not api_key:
                raise PluggyError("Pluggy não retornou apiKey")
            self._api_key = str(api_key)
            self._api_key_expires_at = now + timedelta(minutes=110)
            return self._api_key

    async def _headers(self) -> dict[str, str]:
        return {"accept": "application/json", "X-API-KEY": await self._authenticate()}

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
            detail = str(body.get("code") or response.reason_phrase)
        except ValueError:
            detail = response.reason_phrase
        raise PluggyError(f"Falha ao {operation}: {detail}", status_code=response.status_code)

    async def create_connect_token(self, item_id: str | None = None) -> str:
        payload: dict[str, Any] = {}
        if item_id:
            payload["itemId"] = item_id
        response = await self._client.post(
            "/connect_token", json=payload, headers=await self._headers()
        )
        self._raise_for_status(response, "criar Connect Token")
        token = response.json().get("accessToken")
        if not token:
            raise PluggyError("Pluggy não retornou accessToken")
        return str(token)

    async def get_item(self, item_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/items/{item_id}", headers=await self._headers())
        self._raise_for_status(response, "consultar item")
        return dict(response.json())

    async def list_accounts(self, item_id: str) -> list[dict[str, Any]]:
        response = await self._client.get(
            "/accounts", params={"itemId": item_id}, headers=await self._headers()
        )
        self._raise_for_status(response, "listar contas")
        return [
            dict(value) for value in json.loads(response.text, parse_float=str).get("results", [])
        ]

    async def transaction_pages(self, account_id: str) -> AsyncIterator[list[dict[str, Any]]]:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            params = {"accountId": account_id}
            if cursor:
                params["after"] = cursor
            response = await self._client.get(
                "/v2/transactions", params=params, headers=await self._headers()
            )
            self._raise_for_status(response, "listar transações")
            body = json.loads(response.text, parse_float=str)
            yield [dict(value) for value in body.get("results", [])]
            next_cursor = body.get("cursor")
            if not next_cursor:
                break
            next_cursor = str(next_cursor)
            if next_cursor in seen_cursors:
                raise PluggyError("Cursor repetido recebido da Pluggy")
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    async def list_all_transactions(self, account_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        async for page in self.transaction_pages(account_id):
            result.extend(page)
        return result

    async def list_investments(self, item_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            response = await self._client.get(
                "/investments",
                params={"itemId": item_id, "page": page, "pageSize": 500},
                headers=await self._headers(),
            )
            self._raise_for_status(response, "listar investimentos")
            body = json.loads(response.text, parse_float=str)
            rows = body.get("results", [])
            result.extend(rows)
            if not rows or page >= body.get("totalPages", page):
                return result
            page += 1

    async def investment_transaction_pages(
        self, investment_id: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        page = 1
        while True:
            response = await self._client.get(
                f"/investments/{investment_id}/transactions",
                params={"page": page, "pageSize": 500},
                headers=await self._headers(),
            )
            self._raise_for_status(response, "listar movimentações de investimento")
            body = json.loads(response.text, parse_float=str)
            rows = body.get("results", [])
            yield rows
            if not rows or page >= body.get("totalPages", page):
                return
            page += 1
