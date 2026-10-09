"""Embedding backends for the intent router.

    settings = load_settings()
    embedder = make_embedder("gemma", settings)
    vectors = embedder.embed(["what's my balance"])   # (1, 768), unit-length rows
"""

from src.config import Settings
from src.embeddings.base import Embedder, EmbeddingError, QuotaExceededError
from src.embeddings.gemini import GeminiEmbedder
from src.embeddings.gemma import GemmaEmbedder
from src.embeddings.gemma_ft import GemmaFtEmbedder

BACKENDS = ("gemma", "gemma-ft", "gemini")
# Encoders trained on train.json: evaluation tunes their dials on the held-out calibration split.
FINETUNED_BACKENDS = ("gemma-ft",)


def make_embedder(backend: str, settings: Settings) -> Embedder:
    if backend == "gemma":
        return GemmaEmbedder(settings.gemma, settings.embedding)
    if backend == "gemma-ft":
        return GemmaFtEmbedder(settings.gemma, settings.embedding, settings.finetune)
    if backend == "gemini":
        return GeminiEmbedder(settings.gemini, settings.embedding)
    raise ValueError(f"backend must be one of {BACKENDS}, got {backend!r}")


__all__ = [
    "BACKENDS",
    "FINETUNED_BACKENDS",
    "Embedder",
    "EmbeddingError",
    "GeminiEmbedder",
    "GemmaEmbedder",
    "GemmaFtEmbedder",
    "QuotaExceededError",
    "make_embedder",
]
