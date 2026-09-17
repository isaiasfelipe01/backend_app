from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    budgets,
    categories,
    credit_cards,
    financial_accounts,
    pluggy,
    summary,
    transactions,
    webhooks,
)
from app.utils.logging import configure_logging
from app.routers import investments


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


app = FastAPI(
    title="MeuFinanças API",
    version="1.0.0",
    description="API financeira pessoal com sincronização idempotente Pluggy/Open Finance.",
    lifespan=lifespan,
)

if get_settings().api_env == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

for api_router in (
    categories.router,
    transactions.router,
    credit_cards.router,
    budgets.router,
    summary.router,
    financial_accounts.router,
    pluggy.router,
    webhooks.router,
    investments.router,
):
    app.include_router(api_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": get_settings().api_env}
