"""FastAPI application factory. The ASGI entry point is bankchat.main:app."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bankchat.api import accounts, actions, auth, chat, health, transactions
from bankchat.api.errors import register_error_handlers
from bankchat.db.session import make_engine, make_session_factory
from bankchat.logging_config import configure_logging
from bankchat.router_client.factory import build_router_client
from bankchat.services.chat import ChatContext
from bankchat.services.transfer_help import load_transfer_faq
from bankchat.settings import Settings, get_settings
from bankchat.slots.bank_directory import load_bank_directory

log = logging.getLogger(__name__)

API_PREFIX = "/api"
APP_TITLE = "Benki Yetu chat banking (simulation)"


def _api_router() -> APIRouter:
    api = APIRouter(prefix=API_PREFIX)
    for module in (auth, accounts, transactions, chat, actions, health):
        api.include_router(module.router)
    return api


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        # Loaded once: the gemma router takes several seconds and ~1.5 GB of RAM.
        app.state.chat_context = ChatContext(
            settings=settings,
            router=build_router_client(settings),
            bank=load_bank_directory(settings.bank_config_path),
            faq=load_transfer_faq(settings.transfer_faq_path),
        )
        log.info("backend ready: router_mode=%s", settings.router_mode)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=APP_TITLE, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(_api_router())
    return app

