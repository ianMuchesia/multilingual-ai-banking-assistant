"""Build the RouterClient selected by ROUTER_MODE. Called once at startup."""

import importlib
import logging
import sys
from pathlib import Path

from bankchat.router_client.base import RouterClient
from bankchat.router_client.stub import StubRouterClient
from bankchat.settings import Settings
from bankchat.slots.bank_directory import load_bank_directory

log = logging.getLogger(__name__)

GEMMA_MODULE = "bankchat.router_client.gemma"


def _put_on_path(folder: Path) -> None:
    if not (folder / "src" / "router.py").exists():
        raise RuntimeError(f"INTENT_ROUTER_DIR={folder} does not contain src/router.py")
    entry = str(folder.resolve())
    if entry not in sys.path:
        sys.path.insert(0, entry)


def build_router_client(settings: Settings) -> RouterClient:
    if settings.router_mode == "stub":
        log.info("router mode: stub (keyword rules, no model)")
        return StubRouterClient(load_bank_directory(settings.bank_config_path))
    _put_on_path(settings.intent_router_dir)
    # Imported here on purpose: the gemma module pulls in torch and the model, which
    # stub mode (frontend dev, CI, tests) must not need.
    gemma = importlib.import_module(GEMMA_MODULE)
    return gemma.GemmaRouterClient(settings.gemma_backend, settings.gemma_local_only)
