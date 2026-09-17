import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.pluggy.client import PluggyClient, PluggyError


@pytest.mark.asyncio
async def test_complete_cursor_pagination() -> None:
    cursors = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "temporary"})
        cursor = request.url.params.get("after")
        cursors.append(cursor)
        pages = {None: ({"id": "1"}, "a"), "a": ({"id": "2"}, "b"), "b": ({"id": "3"}, None)}
        row, next_cursor = pages[cursor]
        return httpx.Response(200, json={"results": [row], "cursor": next_cursor})

    settings = Settings(pluggy_client_id="id", pluggy_client_secret=SecretStr("secret"))
    async with PluggyClient(settings, httpx.MockTransport(handler)) as client:
        result = await client.list_all_transactions("account")
    assert [r["id"] for r in result] == ["1", "2", "3"]
    assert cursors == [None, "a", "b"]


@pytest.mark.asyncio
async def test_repeated_cursor_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "key"})
        return httpx.Response(200, json={"results": [], "cursor": "same"})

    async with PluggyClient(
        Settings(pluggy_client_id="id", pluggy_client_secret=SecretStr("s")),
        httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(PluggyError):
            await client.list_all_transactions("a")


@pytest.mark.asyncio
async def test_auth_error_does_not_expose_secret() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    async with PluggyClient(
        Settings(pluggy_client_id="id", pluggy_client_secret=SecretStr("very-secret")),
        httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(PluggyError) as caught:
            await client.list_accounts("x")
    assert "very-secret" not in str(caught.value)
