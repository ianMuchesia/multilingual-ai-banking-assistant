"""Decide what to do with a customer message. The router never executes anything.

    message -> embed -> score every intent -> rules (bank, statement) -> decide() -> route

Routes:
    direct   view / info intent, confident             -> answer it
    confirm  money-moving intent, confident            -> ask the customer to confirm first
    reject   outside the catalog (category "none")     -> politely decline
    llm      not confident, ambiguous, or an action
             phrased as a question                     -> let the LLM decide (step 5)

`decide()` is a plain function so the evaluation runs exactly the same rules
as the live router.
"""

import time
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from src.config import RouterConfig, Settings
from src.data import load_intent_categories
from src.embeddings import make_embedder
from src.index import EmbeddingIndex, file_sha256
from src.question_guard import question_markers
from src.rules import apply_rules, load_bank_config
from src.scoring import Ranking, make_scorer

NEAREST_EXAMPLES = 3
TOP_INTENTS = 3


class Route(StrEnum):
    DIRECT = "direct"
    CONFIRM = "confirm"
    REJECT = "reject"
    LLM = "llm"


class StaleIndexError(RuntimeError):
    """A cached index doesn't match its source file or the embedder. Rebuild it."""


@dataclass(frozen=True)
class RouteDecision:
    text: str
    intent: str                                       # best-scoring intent (tentative when route is llm)
    route: Route
    score: float                                      # best intent's score
    margin: float                                     # best minus second-best
    top3: Ranking
    nearest_examples: list[tuple[str, str, float]]    # (example text, intent, similarity)
    reasons: list[str]
    latency_ms: float


def decide(
    ranked: Ranking, categories: dict[str, str], config: RouterConfig, markers: list[str]
) -> tuple[Route, list[str]]:
    """The routing rules, in order. `markers` = question markers found in the message.

    1. best < threshold, or best - second < margin   -> llm
    2. action guard: action intent + question markers -> llm
    3. category none                                  -> reject
    4. category action                                -> confirm
    5. otherwise                                      -> direct
    """
    (top, best), (second, runner_up) = ranked[0], ranked[1]
    margin = best - runner_up
    category = categories[top]
    reasons = [f"best intent: {top} ({category}), score {best:.3f}"]

    uncertain = []
    if best < config.threshold:
        uncertain.append(f"low confidence: {best:.3f} < threshold {config.threshold:.2f}")
    if margin < config.margin:
        uncertain.append(f"ambiguous between {top} and {second}: margin {margin:.3f} < {config.margin:.3f}")
    if uncertain:
        return Route.LLM, reasons + uncertain
    reasons.append(f"confident: score >= {config.threshold:.2f}, margin {margin:.3f} >= {config.margin:.3f}")

    if config.action_guard and category == "action" and markers:
        reasons.append(f"action intent but phrased as a question (found: {', '.join(markers)})")
        return Route.LLM, reasons

    if category == "none":
        reasons.append("outside the supported catalog")
        return Route.REJECT, reasons
    if category == "action":
        reasons.append("moves money: customer must confirm")
        return Route.CONFIRM, reasons
    reasons.append(f"{category} intent: safe to answer directly")
    return Route.DIRECT, reasons


def check_index(index: EmbeddingIndex, source_sha256: str, categories: dict[str, str], build_cmd: str) -> None:
    """Raise StaleIndexError if the index wasn't built from this source file or has unknown intents."""
    if index.source_sha256 != source_sha256:
        raise StaleIndexError(f"index is stale: its source file changed since it was built. Run: {build_cmd}")
    unknown = set(index.intents.tolist()) - categories.keys()
    if unknown:
        raise StaleIndexError(f"index has intents not in intents.json: {sorted(unknown)}. Run: {build_cmd}")


class Router:
    def __init__(self, backend: str, settings: Settings, config: RouterConfig) -> None:
        self.backend = backend
        self.config = config
        paths = settings.paths
        build_cmd = f"python -m scripts.build_index --backend {backend}"

        # Cheap checks first, before spending ~9s loading a model.
        index_path = paths.index_file(backend, settings.embedding.dim)
        if not index_path.exists():
            raise StaleIndexError(f"no index at {index_path.name}. Run: {build_cmd}")
        self._index = EmbeddingIndex.load(index_path)
        self._categories = load_intent_categories(paths.intents)
        check_index(self._index, file_sha256(paths.train), self._categories, build_cmd)

        # The SAME embedder that built the index: same model, dim and prefix.
        self._embedder = make_embedder(backend, settings)
        built_with = (self._index.model_id, self._index.dim, self._index.prefix)
        running = (self._embedder.model_id, self._embedder.dim, self._embedder.prefix)
        if built_with != running:
            raise StaleIndexError(
                f"index was built with (model, dim, prefix)={built_with}, "
                f"but the embedder is {running}. Run: {build_cmd} --force"
            )

        self._scorer = make_scorer(config.scoring, self._index.vectors, self._index.intents, config.k)
        self._bank = load_bank_config(paths.bank_config) if config.rules else None

    def route(self, text: str) -> RouteDecision:
        started = time.perf_counter()
        query = self._embedder.embed([text])[0]
        ranked = self._scorer.rank(query)
        rule_reasons: list[str] = []
        if self._bank:
            ranked, rule_reasons = apply_rules(ranked, text, self._bank)
        route, reasons = decide(ranked, self._categories, self.config, question_markers(text))
        reasons = rule_reasons + reasons

        sims = self._index.vectors @ query
        nearest = np.argsort(sims)[::-1][:NEAREST_EXAMPLES]
        return RouteDecision(
            text=text,
            intent=ranked[0][0],
            route=route,
            score=ranked[0][1],
            margin=ranked[0][1] - ranked[1][1],
            top3=ranked[:TOP_INTENTS],
            nearest_examples=[
                (str(self._index.texts[i]), str(self._index.intents[i]), float(sims[i])) for i in nearest
            ],
            reasons=reasons,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
