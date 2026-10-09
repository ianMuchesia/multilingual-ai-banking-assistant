"""The real intent router (EmbeddingGemma, local CPU), wrapped in the RouterClient interface.

Importing this module imports intent-router's `src` package, torch and sentence-transformers,
so only the factory imports it, and only when ROUTER_MODE=gemma. intent-router's folder must
be on sys.path first (the factory does that).
"""

import logging
import threading

from src.config import load_router_config, load_settings, with_overrides
from src.router import Router

from bankchat.router_client.base import RouterDecision

log = logging.getLogger(__name__)


class GemmaRouterClient:
    mode = "gemma"

    def __init__(self, backend: str, local_only: bool) -> None:
        settings = with_overrides(load_settings(), gemma_local_only=local_only)
        config = load_router_config(settings.paths.router_config, backend)
        log.info("loading intent router: backend=%s scoring=%s local_only=%s", backend, config.scoring, local_only)
        self._router = Router(backend, settings, config)
        # FastAPI runs sync endpoints in a thread pool; one embedding at a time keeps the model safe.
        self._lock = threading.Lock()

    def route(self, text: str) -> RouterDecision:
        with self._lock:
            decision = self._router.route(text)
        return RouterDecision(
            intent=decision.intent,
            route=str(decision.route.value),
            score=float(decision.score),
            margin=float(decision.margin),
            top3=[(str(intent), float(score)) for intent, score in decision.top3],
            nearest_examples=[(str(t), str(i), float(s)) for t, i, s in decision.nearest_examples],
            reasons=list(decision.reasons),
            latency_ms=float(decision.latency_ms),
        )
