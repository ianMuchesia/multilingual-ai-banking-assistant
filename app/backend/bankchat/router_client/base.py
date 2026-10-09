"""The one interface the backend uses to route a message, whatever runs behind it."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RouterDecision:
    """Same shape as intent-router's RouteDecision, with plain JSON-friendly values."""

    intent: str
    route: str                                          # direct | confirm | reject | llm
    score: float
    margin: float
    top3: list[tuple[str, float]]
    nearest_examples: list[tuple[str, str, float]]      # (example text, intent, similarity)
    reasons: list[str]
    latency_ms: float


class RouterClient(Protocol):
    mode: str

    def route(self, text: str) -> RouterDecision: ...
